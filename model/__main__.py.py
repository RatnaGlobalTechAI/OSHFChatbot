from .argparse_wrapper import get_parsed_args


def main(argv=None):
    args = get_parsed_args(argv=argv)
    args.run_command(args=args)