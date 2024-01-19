
import hashlib
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass
from importlib.metadata import metadata, version
from pathlib import Path

import ipinfo
import openai
from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    level=os.environ.get("LOGLEVEL", os.environ.get("LOGURU_LEVEL", "INFO")),
)


@dataclass
class GeneralDefinitions:

    SYSTEM_ENV_OPENAI_API_KEY: str = None

    RUN_ID = uuid.uuid4().hex
    PACKAGE_NAME = __name__
    VERSION = version(__name__)
    PACKAGE_DESCRIPTION = metadata(__name__)["Summary"]

    PACKAGE_DIRECTORY = Path(__file__).parent
    _PACKAGE_TMPDIR = tempfile.TemporaryDirectory()
    PACKAGE_TMPDIR = Path(_PACKAGE_TMPDIR.name)

    APP_NAME = "pyRobBot"
    APP_DIR = PACKAGE_DIRECTORY / "app"
    APP_PATH = APP_DIR / "app.py"
    PARSED_ARGS_FILE = PACKAGE_TMPDIR / f"parsed_args_{RUN_ID}.pkl"

    IPINFO = ipinfo.getHandler().getDetails().all

    @staticmethod
    def openai_key_hash():
        try:
            client = openai.OpenAI()
        except openai.OpenAIError:
            api_key = None
        else:
            api_key = client.api_key
        if api_key is None:
            return "demo"
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @property
    def package_cache_directory(self):
        return Path.home() / ".cache" / self.PACKAGE_NAME

    @property
    def current_user_cache_dir(self):
        return self.package_cache_directory / f"user_{self.openai_key_hash()}"

    @property
    def chats_storage_dir(self):
        return self.current_user_cache_dir / "chats"


GeneralConstants = GeneralDefinitions(
    SYSTEM_ENV_OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY")
)
