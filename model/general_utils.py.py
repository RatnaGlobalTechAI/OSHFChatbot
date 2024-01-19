import inspect
import json
import time
from functools import wraps
from pathlib import Path
from typing import Optional

import httpx
import openai
from loguru import logger


class ReachedMaxNumberOfAttemptsError(Exception):
    """Error raised when the max number of attempts has been reached."""


def retry(
    max_n_attempts: int = 5,
    handled_errors: tuple[Exception, ...] = (openai.APITimeoutError, httpx.HTTPError),
    error_msg: Optional[str] = None,
):

    def retry_or_fail(error):
        retry_or_fail.execution_count = getattr(retry_or_fail, "execution_count", 0) + 1

        if retry_or_fail.execution_count < max_n_attempts:
            logger.warning(
                "{}. Making new attempt ({}/{})...",
                error,
                retry_or_fail.execution_count + 1,
                max_n_attempts,
            )
            time.sleep(1)
        else:
            raise ReachedMaxNumberOfAttemptsError(error_msg) from error

    def retry_decorator(function):

        @wraps(function)
        def wrapper_f(*args, **kwargs):
            while True:
                try:
                    return function(*args, **kwargs)
                except handled_errors as error:  # noqa: PERF203
                    retry_or_fail(error=error)

        @wraps(function)
        def wrapper_generator_f(*args, **kwargs):
            success = False
            while not success:
                try:
                    yield from function(*args, **kwargs)
                except handled_errors as error:  # noqa: PERF203
                    retry_or_fail(error=error)
                else:
                    success = True

        return wrapper_generator_f if inspect.isgeneratorfunction(function) else wrapper_f

    return retry_decorator


class AlternativeConstructors:

    @classmethod
    def from_dict(cls, configs: dict):
        return cls(configs=cls.default_configs.model_validate(configs))

    @classmethod
    def from_cli_args(cls, cli_args):
        chat_opts = {
            k: v
            for k, v in vars(cli_args).items()
            if k in cls.default_configs.model_fields and v is not None
        }
        return cls.from_dict(chat_opts)

    @classmethod
    def from_cache(cls, cache_dir: Path):
        try:
            with open(cache_dir / "configs.json", "r") as configs_f:
                new = cls.from_dict(json.load(configs_f))
            with open(cache_dir / "metadata.json", "r") as metadata_f:
                new.metadata = json.load(metadata_f)
                new.id = new.metadata["chat_id"]
        except FileNotFoundError:
            logger.warning(
                "Could not find configs and/or metadata file in cache directory. "
                + f"Creating {cls.__name__} with default configs."
            )
            new = cls()
        return new