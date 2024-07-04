import argparse
import logging
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta

import colorama
import pytimeparse
import sdnotify

from . import dockerapi
from .base import process_event, sweep
from .daemon import install_daemon
from .feedback import init_logging
from .state import State, dump_state, load_state

logger = logging.getLogger("docker_housekeep")
systemd_notifier = sdnotify.SystemdNotifier()


def handle_events(fd, state: State):
    events = dockerapi.get_events(since=state.timestamp or datetime.fromtimestamp(0))
    systemd_notifier.notify("READY=1")

    for event in events:
        process_event(event, state)
        dump_state(state, fd)


class UpdateOrCreateFile(argparse.FileType):
    """Special argparse file type, a combination of x+ and r+.

    - Opens file for reading and writing;
    - Seek position is at the beginning;
    - Creates the file if it does not exist.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, mode="r+", **kwargs)

    def __call__(self, string: str):
        try:
            try:
                return open(string, "x+", self._bufsize, self._encoding, self._errors)
            except FileExistsError:
                fd = open(string, "r+", self._bufsize, self._encoding, self._errors)
                fd.seek(0)
                return fd
        except OSError as e:
            raise argparse.ArgumentTypeError(f"can't open '{string}': {e}")


def timedelta_argument(string: str):
    seconds = pytimeparse.parse(string)
    if seconds is None:
        raise argparse.ArgumentTypeError(f"couldn't understand time duration '{string}'")

    return timedelta(seconds=seconds)


def cli():
    # Shared arguments between subcommands
    def add_argument_verbosity(p):
        p.add_argument(
            "-v",
            "--verbose",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="enable verbose output (default: off)",
        )

    def add_argument_max_age(p):
        p.add_argument(
            "--max-age",
            type=timedelta_argument,
            required=True,
            help="maxiumum allowed age for docker containers, like '3d12h'; older images will be deleted during sweep",
        )

    parser = ArgumentParser()
    parser.add_argument(
        "--log-timestamps", action=argparse.BooleanOptionalAction, default=False, help="print timestamps in logs"
    )

    subcommands = parser.add_subparsers(title="subcommands", dest="subcommand")

    daemon_parser = subcommands.add_parser("daemon")
    daemon_subcommands = daemon_parser.add_subparsers(title="subcommands", dest="daemon_subcommand")

    daemon_install_parser = daemon_subcommands.add_parser("install")
    daemon_install_parser.add_argument(
        "--enable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="start the service and enable it at startup",
    )

    watch_parser = subcommands.add_parser("watch")
    watch_parser.add_argument("--state-file", type=UpdateOrCreateFile(encoding="utf-8"), default="state.json")
    add_argument_verbosity(watch_parser)

    sweep_parser = subcommands.add_parser("sweep")
    sweep_parser.add_argument("--state-file", type=argparse.FileType("r", encoding="utf-8"), default="state.json")
    add_argument_max_age(sweep_parser)
    add_argument_verbosity(sweep_parser)

    return parser


def main():
    colorama.init(autoreset=True)
    args = cli().parse_args()

    init_logging(timestamps=args.log_timestamps)

    if args.subcommand == "daemon":
        if args.daemon_subcommand == "install":
            install_daemon(enable=args.enable)
        else:
            raise RuntimeError("unhandled subcommand of 'daemon'")
    elif args.subcommand == "watch":
        init_logging(verbose=args.verbose, timestamps=args.log_timestamps)

        state = load_state(args.state_file)
        handle_events(args.state_file, state)
    elif args.subcommand == "sweep":
        init_logging(verbose=args.verbose, timestamps=args.log_timestamps)

        state = load_state(args.state_file)
        sweep(state, args.max_age)
    else:
        raise RuntimeError("unhandled subcommand")


if __name__ == "__main__":
    sys.exit(main())
