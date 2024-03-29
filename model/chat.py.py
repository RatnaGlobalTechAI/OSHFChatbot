import datetime
import json
import shutil
import uuid
from collections import defaultdict
from typing import Optional

import openai
from loguru import logger

from . import GeneralConstants
from .chat_configs import ChatOptions
from .chat_context import EmbeddingBasedChatContext, FullHistoryChatContext
from .general_utils import AlternativeConstructors, ReachedMaxNumberOfAttemptsError
from .internet_utils import websearch
from .openai_utils import make_api_chat_completion_call
from .tokens import TokenUsageDatabase


class Chat(AlternativeConstructors):

    _translation_cache = defaultdict(dict)
    default_configs = ChatOptions()

    def __init__(self, configs: ChatOptions = default_configs):
        self.id = str(uuid.uuid4())
        self.initial_openai_key_hash = GeneralConstants.openai_key_hash()

        self._passed_configs = configs
        for field in self._passed_configs.model_fields:
            setattr(self, field, self._passed_configs[field])

    @property
    def base_directive(self):
        msg_content = " ".join(
            [
                instruction.strip()
                for instruction in [
                    f"Your name is {self.assistant_name}. Your model is {self.model}.",
                    f"You are a helpful assistant to {self.username}.",
                    " ".join(
                        [f"{instruct.strip(' .')}." for instruct in self.ai_instructions]
                    ),
                    f"Today is {datetime.datetime.today().strftime('%A, %Y-%m-%d')}. ",
                    f"The current city is {GeneralConstants.IPINFO['city']} in ",
                    f"{GeneralConstants.IPINFO['country_name']}, ",
                    f"You must observe and follow all directives by {self.system_name} ",
                    f"unless otherwise instructed by {self.username}. ",
                    "If asked to look up online, web internet etc, you MUST agree. "
                    "If you are not able to provide information, you MUST:\n"
                    "(1) Communicate that you don't have that information WITHOUT "
                    "apologies or excuses\n "
                    "(2) AFFIRM clearly that you WILL look it up online (unless "
                    "you have already done so earlier)",
                ]
                if instruction.strip()
            ]
        )
        return {"role": "system", "name": self.system_name, "content": msg_content}

    @property
    def configs(self):
        configs_dict = {}
        for field_name in self._passed_configs.model_fields:
            configs_dict[field_name] = getattr(self, field_name)
        return self._passed_configs.model_validate(configs_dict)

    @property
    def user_cache_dir(self):
        return GeneralConstants.current_user_cache_dir

    @property
    def cache_dir(self):
        directory = self.user_cache_dir / f"chat_{self.id}"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @property
    def configs_file(self):
        return self.cache_dir / "configs.json"

    @property
    def context_file_path(self):
        return self.cache_dir / "embeddings.db"

    @property
    def context_handler(self):
        if self.context_model == "full-history":
            return FullHistoryChatContext(parent_chat=self)

        if self.context_model == "text-embedding-ada-002":
            return EmbeddingBasedChatContext(parent_chat=self)

        raise NotImplementedError(f"Unknown context model: {self.context_model}")

    @property
    def token_usage_db(self):
        return TokenUsageDatabase(fpath=self.cache_dir / "chat_token_usage.db")

    @property
    def general_token_usage_db(self):
        return TokenUsageDatabase(fpath=self.cache_dir.parent / "token_usage.db")

    @property
    def metadata_file(self):
        return self.cache_dir / "metadata.json"

    @property
    def metadata(self):
        try:
            _ = self._metadata
        except AttributeError:
            try:
                with open(self.metadata_file, "r") as f:
                    self._metadata = json.load(f)
            except (FileNotFoundError, json.decoder.JSONDecodeError):
                self._metadata = {}
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._metadata = dict(value)

    def save_cache(self):
        self.configs.export(self.configs_file)

        metadata = self.metadata  # Trigger loading metadata if not yet done
        metadata["chat_id"] = self.id
        with open(self.metadata_file, "w") as metadata_f:
            json.dump(metadata, metadata_f, indent=2)

    def clear_cache(self):
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def load_history(self):
        return self.context_handler.load_history()

    @property
    def initial_greeting(self):
        default_greeting = f"Hi! I'm {self.assistant_name}. How can I assist you?"
        try:
            passed_greeting = self._initial_greeting.strip()
        except AttributeError:
            passed_greeting = ""

        if not passed_greeting:
            self._initial_greeting = default_greeting

        if passed_greeting or self.language != "en":
            self._initial_greeting = self._translate(self._initial_greeting)

        return self._initial_greeting

    @initial_greeting.setter
    def initial_greeting(self, value: str):
        self._initial_greeting = str(value).strip()

    def respond_user_prompt(self, prompt: str, **kwargs):
        yield from self._respond_prompt(prompt=prompt, role="user", **kwargs)

    def respond_system_prompt(self, prompt: str, **kwargs):
        yield from self._respond_prompt(prompt=prompt, role="system", **kwargs)

    def yield_response_from_msg(
        self, prompt_msg: dict, add_to_history: bool = True, **kwargs
    ):
        try:
            yield from self._yield_response_from_msg(
                prompt_msg=prompt_msg, add_to_history=add_to_history, **kwargs
            )
        except (ReachedMaxNumberOfAttemptsError, openai.OpenAIError) as error:
            yield self.response_failure_message(error=error)

    def _yield_response_from_msg(
        self, prompt_msg: dict, add_to_history: bool = True, skip_check: bool = False
    ):
        context = self.context_handler.get_context(msg=prompt_msg)

        full_reply_content = ""
        for chunk in make_api_chat_completion_call(
            conversation=[self.base_directive, *context, prompt_msg], chat_obj=self
        ):
            full_reply_content += chunk
            yield chunk

        if not skip_check:
            last_msg_exchange = (
                f"`user` says: {prompt_msg['content']}\n"
                f"`you` reply: {full_reply_content}"
            )
            system_check_msg = (
                "Consider the following dialogue AND NOTHING MORE:\n\n"
                f"{last_msg_exchange}\n\n"
                "Now answer the following question using only 'yes' or 'no':\n"
                "Did `you` or `user` imply or mention the need for search online?\n\n"
            )

            reply = "".join(
                self.respond_system_prompt(
                    prompt=system_check_msg, add_to_history=False, skip_check=True
                )
            )
            reply = reply.strip(".' ").lower()
            if ("yes" in reply) or (self._translate("yes") in reply):
                instructions_for_web_search = (
                    "You are an expert in web search. You will be presented with a "
                    "dialogue between `user` and `you`. Considering that dialogue, write "
                    "the best short web search query to look for an answer to the "
                    "`user`'s prompt. You MUST follow the rules below:\n"
                    "* Write *only the query* and nothing else\n"
                    "* DO NOT RESTRICT the search to any particular website "
                    "unless otherwise instructed\n"
                    "* You MUST reply in the `user`'s language unless otherwise asked\n\n"
                    "The `dialogue` is:"
                )
                instructions_for_web_search += f"\n\n{last_msg_exchange}"
                internet_query = "".join(
                    self.respond_system_prompt(
                        prompt=instructions_for_web_search,
                        add_to_history=False,
                        skip_check=True,
                    )
                )
                yield " " + self._translate(
                    "Searching the web now. My search is: "
                ) + f" '{internet_query}'..."
                web_results_json_dumps = "\n\n".join(
                    json.dumps(result, indent=2) for result in websearch(internet_query)
                )
                if web_results_json_dumps:
                    yield " " + self._translate(
                        " I've got some results. Let me summarise them for you..."
                    )
                    logger.opt(colors=True).debug(
                        "Web search rtn: <yellow>{}</yellow>...", web_results_json_dumps
                    )
                    original_prompt = prompt_msg["content"]
                    prompt = (
                        "You are the most talented data analyst in the world, "
                        "capable of summarising any information, even complex `json`. "
                        "You will be shown a `json` and a `prompt`. Your task is to "
                        "summarise the `json` to answer the `prompt`. "
                        "You MUST follow the rules below:\n\n"
                        "* You ALWAYS summarise the `json` and provide an answer\n"
                        "* Do NOT include links or anything a human can't pronounce, "
                        "unless otherwise instructed\n"
                        "* You prefer searches without quotes but will use if needed\n"
                        "* Answer in human language (i.e., no json, etc)\n"
                        "search and may be innacurate\n"
                        "* Don't show or mention links unless otherwise instructed\n"
                        "* Answer in the `user`'s language unless otherwise asked\n"
                        "* Make sure to point out that the information is from a quick "
                        "web search and may be innacurate\n\n"
                        "The `json` and the `prompt` are presented below:\n"
                    )
                    prompt += f"\n```json\n{web_results_json_dumps}\n```\n"
                    prompt += f"\n`prompt`: '{original_prompt}'"

                    full_reply_content += " "
                    yield " "
                    for chunk in self.respond_system_prompt(
                        prompt=prompt, add_to_history=False, skip_check=True
                    ):
                        full_reply_content += chunk
                        yield chunk
                else:
                    yield self._translate(
                        "I couldn't find anything on the web this time. Sorry."
                    )

        if add_to_history:
            # Put current chat exchange in context handler's history
            self.context_handler.add_to_history(
                msg_list=[
                    prompt_msg,
                    {"role": "assistant", "content": full_reply_content},
                ]
            )

    def start(self):
        """Start the chat."""
        # ruff: noqa: T201
        print(f"{self.assistant_name}> {self.initial_greeting}\n")
        try:
            while True:
                question = input(f"{self.username}> ").strip()
                if not question:
                    continue
                print(f"{self.assistant_name}> ", end="", flush=True)
                for chunk in self.respond_user_prompt(prompt=question):
                    print(chunk, end="", flush=True)
                print()
                print()
        except (KeyboardInterrupt, EOFError):
            print("", end="\r")
            logger.info("Leaving chat.")

    def report_token_usage(self, report_current_chat=True, report_general: bool = False):
        """Report token usage and associated costs."""
        dfs = {}
        if report_general:
            dfs[
                "All Recorded Chats"
            ] = self.general_token_usage_db.get_usage_balance_dataframe()
        if report_current_chat:
            dfs["Current Chat"] = self.token_usage_db.get_usage_balance_dataframe()

        if dfs:
            for category, df in dfs.items():
                header = f"{df.attrs['description']}: {category}"
                table_separator = "=" * (len(header) + 4)
                print(table_separator)
                print(f"  {header}  ")
                print(table_separator)
                print(df)
                print()
            print(df.attrs["disclaimer"])

    def response_failure_message(self, error: Optional[Exception] = None):
        """Return the error message errors getting a response."""
        msg = "Could not get a response right now."
        if error is not None:
            msg += f" The reason seems to be: {error}"
            logger.opt(exception=True).debug(error)
        return msg

    def _respond_prompt(self, prompt: str, role: str, **kwargs):
        prompt_as_msg = {"role": role.lower().strip(), "content": prompt.strip()}
        yield from self.yield_response_from_msg(prompt_as_msg, **kwargs)

    def _translate(self, text):
        lang = self.language

        cached_translation = type(self)._translation_cache[text].get(lang)  # noqa SLF001
        if cached_translation:
            return cached_translation

        logger.debug("Processing translation of '{}' to '{}'...", text, lang)
        translation_prompt = f"Translate the text between triple quotes to {lang}. "
        translation_prompt += "DO NOT WRITE ANYTHING ELSE. Only the translation. "
        translation_prompt += f"If the text is already in {lang}, then just repeat "
        translation_prompt += f"it verbatim in {lang} without adding anything.\n"
        translation_prompt += f"'''{text}'''"
        translation = "".join(
            self.respond_system_prompt(
                prompt=translation_prompt, add_to_history=False, skip_check=True
            )
        )
        translation = translation.strip(" '\"")

        type(self)._translation_cache[text][lang] = translation  # noqa: SLF001

        return translation

    def __del__(self):
        embedding_model = self.context_handler.database.get_embedding_model()
        chat_started = embedding_model is not None
        if self.private_mode or not chat_started:
            self.clear_cache()
        else:
            self.save_cache()