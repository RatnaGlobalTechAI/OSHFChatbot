from typing import TYPE_CHECKING

import openai

from .chat_configs import OpenAiApiCallOptions
from .general_utils import retry
from .tokens import get_n_tokens_from_msgs

if TYPE_CHECKING:
    from .chat import Chat


def make_api_chat_completion_call(conversation: list, chat_obj: "Chat"):
    api_call_args = {}
    for field in OpenAiApiCallOptions.model_fields:
        if getattr(chat_obj, field) is not None:
            api_call_args[field] = getattr(chat_obj, field)

    @retry(error_msg="Problems connecting to OpenAI API")
    def stream_reply(conversation, **api_call_args):
        # Update the chat's token usage database with tokens used in chat input
        # Do this here because every attempt consumes tokens, even if it fails
        n_tokens = get_n_tokens_from_msgs(messages=conversation, model=chat_obj.model)
        for db in [chat_obj.general_token_usage_db, chat_obj.token_usage_db]:
            db.insert_data(model=chat_obj.model, n_input_tokens=n_tokens)

        full_reply_content = ""
        for completion_chunk in openai.chat.completions.create(
            messages=conversation, stream=True, **api_call_args
        ):
            reply_chunk = getattr(completion_chunk.choices[0].delta, "content", "")
            if reply_chunk is None:
                break
            full_reply_content += reply_chunk
            yield reply_chunk

        # Update the chat's token usage database with tokens used in chat output
        reply_as_msg = {"role": "assistant", "content": full_reply_content}
        n_tokens = get_n_tokens_from_msgs(messages=[reply_as_msg], model=chat_obj.model)
        for db in [chat_obj.general_token_usage_db, chat_obj.token_usage_db]:
            db.insert_data(model=chat_obj.model, n_output_tokens=n_tokens)

    yield from stream_reply(conversation, **api_call_args)