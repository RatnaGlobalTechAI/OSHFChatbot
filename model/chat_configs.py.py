import argparse
import json
import types
import typing
from getpass import getuser
from pathlib import Path
from typing import Literal, Optional, get_args, get_origin

from pydantic import BaseModel, Field

from pyrobbot import GeneralConstants


class BaseConfigModel(BaseModel, extra="forbid"):

    @classmethod
    def get_allowed_values(cls, field: str):
        annotation = cls._get_field_param(field=field, param="annotation")
        if isinstance(annotation, type(Literal[""])):
            return get_args(annotation)
        return None

    @classmethod
    def get_type(cls, field: str):
        type_hint = typing.get_type_hints(cls)[field]
        if isinstance(type_hint, type):
            if isinstance(type_hint, types.GenericAlias):
                return get_origin(type_hint)
            return type_hint
        type_hint_first_arg = get_args(type_hint)[0]
        if isinstance(type_hint_first_arg, type):
            return type_hint_first_arg
        return None

    @classmethod
    def get_default(cls, field: str):
        return cls.model_fields[field].get_default()

    @classmethod
    def get_description(cls, field: str):
        return cls._get_field_param(field=field, param="description")

    @classmethod
    def from_cli_args(cls, cli_args: argparse.Namespace):
        relevant_args = {
            k: v
            for k, v in vars(cli_args).items()
            if k in cls.model_fields and v is not None
        }
        return cls.model_validate(relevant_args)

    @classmethod
    def _get_field_param(cls, field: str, param: str):
        return getattr(cls.model_fields[field], param, None)

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError as error:
            raise KeyError(item) from error

    def export(self, fpath: Path):
        with open(fpath, "w") as configs_file:
            configs_file.write(self.model_dump_json(indent=2, exclude_unset=True))

    @classmethod
    def from_file(cls, fpath: Path):
        with open(fpath, "r") as configs_file:
            return cls.model_validate(json.load(configs_file))


class OpenAiApiCallOptions(BaseConfigModel):

    _openai_url = "https://platform.openai.com/docs/api-reference/chat/create#chat-create"
    _models_url = "https://platform.openai.com/docs/models"

    model: Literal[
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-16k",  # Will point to gpt-3.5-turbo-1106 starting Dec 11, 2023
        "gpt-3.5-turbo",  # Will point to gpt-3.5-turbo-1106 starting Dec 11, 2023
        "gpt-4-1106-preview",
        "gpt-4",
    ] = Field(
        default="gpt-3.5-turbo-1106",
        description=f"OpenAI LLM model to use. See {_openai_url}-model and {_models_url}",
    )
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description=f"See <{_openai_url}-max_tokens>"
    )
    presence_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description=f"See <{_openai_url}-presence_penalty>"
    )
    frequency_penalty: Optional[float] = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description=f"See <{_openai_url}-frequency_penalty>",
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description=f"See <{_openai_url}-temperature>"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description=f"See <{_openai_url}-top_p>"
    )
    timeout: Optional[float] = Field(
        default=10.0, gt=0.0, description="Timeout for API requests in seconds"
    )


class ChatOptions(OpenAiApiCallOptions):

    username: str = Field(default=getuser(), description="Name of the chat's user")
    assistant_name: str = Field(default="Rob", description="Name of the chat's assistant")
    system_name: str = Field(
        default=f"{GeneralConstants.PACKAGE_NAME}_system",
        description="Name of the chat's system",
    )
    ai_instructions: tuple[str, ...] = Field(
        default=(
            "You answer correctly.",
            "You do not lie.",
        ),
        description="Initial instructions for the AI",
    )
    context_model: Literal["text-embedding-ada-002", "full-history"] = Field(
        default="text-embedding-ada-002",
        description=(
            "Model to use for chat context (~memory). "
            + "Once picked, it cannot be changed."
        ),
        json_schema_extra={"frozen": True},
    )
    initial_greeting: Optional[str] = Field(
        default="", description="Initial greeting given by the assistant"
    )
    private_mode: Optional[bool] = Field(
        default=None,
        description="Toggle private mode. If this flag is used, the chat will not "
        + "be logged and the chat history will not be saved.",
    )
    api_connection_max_n_attempts: int = Field(
        default=5,
        gt=0,
        description="Maximum number of attempts to connect to the OpenAI API",
    )
    language: str = Field(
        default="en",
        description="Initial language adopted by the assistant. Use either the ISO-639-1 "
        "format (e.g. 'pt'), or an RFC5646 language tag (e.g. 'pt-br').",
    )


class VoiceAssistantConfigs(BaseConfigModel):

    tts_engine: Literal["openai", "google"] = Field(
        default="openai",
        description="The text-to-speech engine to use. The `google` engine is free "
        "(for now, at least), but the `openai` engine (which will charge from your "
        "API credits) sounds more natural.",
    )
    stt_engine: Literal["openai", "google"] = Field(
        default="google",
        description="The preferred speech-to-text engine to use. The `google` engine is "
        "free (for now, at least); the `openai` engine is less succeptible to outages.",
    )
    openai_tts_voice: Literal[
        "alloy", "echo", "fable", "onyx", "nova", "shimmer"
    ] = Field(default="onyx", description="Voice to use for OpenAI's TTS")
    exit_expressions: list[str] = Field(
        default=["bye-bye", "ok bye-bye", "okay bye-bye"],
        description="Expression(s) to use in order to exit the chat",
    )

    inactivity_timeout_seconds: int = Field(
        default=1,
        gt=0,
        description="How much time user should be inactive "
        "for the assistant to stop listening",
    )
    speech_likelihood_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Accept audio as speech if the likelihood is above this threshold",
    )
    # sample_rate and frame_duration have to be consistent with the values uaccepted by
    # the webrtcvad package
    sample_rate: Literal[8000, 16000, 32000, 48000] = Field(
        default=32000, description="Sample rate for audio recording, in Hz."
    )
    frame_duration: Literal[10, 20, 30] = Field(
        default=30, description="Frame duration for audio recording, in milliseconds."
    )
    skip_initial_greeting: Optional[bool] = Field(
        default=None, description="Skip initial greeting."
    )


class VoiceChatConfigs(ChatOptions, VoiceAssistantConfigs):
    """Model for the voice chat's configuration options."""