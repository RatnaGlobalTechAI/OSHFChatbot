import subprocess

from loguru import logger

from . import GeneralConstants
from .chat import Chat
from .chat_configs import ChatOptions
from .voice_chat import VoiceChat


def voice_chat(args):
    VoiceChat.from_cli_args(cli_args=args).start()


def browser_chat(args):
    ChatOptions.from_cli_args(args).export(fpath=GeneralConstants.PARSED_ARGS_FILE)
    try:
        subprocess.run(
            [  # noqa: S603, S607
                "streamlit",
                "run",
                GeneralConstants.APP_PATH.as_posix(),
                "--",
                GeneralConstants.PARSED_ARGS_FILE.as_posix(),
            ],
            cwd=GeneralConstants.APP_DIR.as_posix(),
            check=True,
        )
    except (KeyboardInterrupt, EOFError):
        logger.info("Exiting.")


def terminal_chat(args):
    chat = Chat.from_cli_args(cli_args=args)
    chat.start()
    if args.report_accounting_when_done:
        chat.report_token_usage(report_general=True)


def accounting_report(args):
    chat = Chat.from_cli_args(cli_args=args)
    chat.private_mode = True
    chat.report_token_usage(report_general=True, report_current_chat=False)