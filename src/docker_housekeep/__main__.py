import argparse
import asyncio
import logging
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta

import colorama
import pytimeparse
import sdnotify
import yaml
from croniter import croniter

from . import config as config_mod
from . import dockerapi
from . import state as state_mod
from .base import process_event, sweep
from .config import Config
from .daemon import install_daemon
from .feedback import init_logging
from .state import State

logger = logging.getLogger("docker_housekeep")
systemd_notifier = sdnotify.SystemdNotifier()


async def async_iterate(sync_iterable):
    """Convert a syncronized iterable into an async one.

    Taken from https://stackoverflow.com/q/76991812
    """
    # to_thread errors if StopIteration raised in it. So we use a sentinel to detect the end
    done_sentinel = object()
    it = iter(sync_iterable)
    while (value := await asyncio.to_thread(next, it, done_sentinel)) is not done_sentinel:
        yield value


async def handle_events(state: State, state_fd):
    events = dockerapi.get_events(since=state.timestamp or datetime.fromtimestamp(0))
    logger.info("watching docker events")

    async for event in async_iterate(events):
        process_event(event, state)

        state_fd.seek(0)
        state_mod.dump(state, state_fd)
        state_fd.truncate()


async def periodic_sweep(config: Config, state: State):
    while True:
        now = datetime.now()
        sweep_time = croniter(config.sweep_schedule, start_time=now).get_next(ret_type=datetime)
        logger.info("scheduled next sweep for %s", sweep_time.strftime("%Y-%m-%d %H:%M:%S"))
        await asyncio.sleep((sweep_time - now).total_seconds())
        sweep(state, config.max_age)


async def watch(*, config: Config, state: State, state_fd, do_sweep=True):
    async with asyncio.TaskGroup() as group:
        group.create_task(handle_events(state, state_fd))

        if do_sweep:
            group.create_task(periodic_sweep(config, state))

        systemd_notifier.notify("READY=1")


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


from io import BytesIO, StringIO


class ReadFileOrString(argparse.FileType):
    """Special argparse file type, which opens in "r" or "rb" mode but provides a default StringIO/BytesIO from the
    `default` argument of __init__ if the file is missing.
    """

    def __init__(self, *args, default: str | bytes, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._default = default

    def __call__(self, string: str):
        try:
            return open(string, self._mode, self._bufsize, self._encoding, self._errors)
        except FileNotFoundError:
            if "b" in self._mode:
                return BytesIO(self._default)
            return StringIO(self._default)
        except OSError as e:
            raise argparse.ArgumentTypeError(f"can't open '{string}': {e}")


def timedelta_argument(string: str):
    seconds = pytimeparse.parse(string)
    if seconds is None:
        raise argparse.ArgumentTypeError(f"couldn't understand time duration '{string}'")

    return timedelta(seconds=seconds)


def validate_timedelta_argument(string: str):
    """Same as `timedelta_argument`, except discards parsed result and returns the original string."""
    timedelta_argument(string)
    return string


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

    def add_argument_config(p):
        p.add_argument(
            "-c",
            "--config",
            type=ReadFileOrString("r", encoding="utf-8", default=config_mod.dumps(config_mod.default_config)),
            default="/etc/docker-housekeep.conf",
            help="configuration file path; see documentation for more information on configuration values (default: /etc/docker-housekeep.conf)",
        )

    state_file_help = "path where collected image history is stored (default: state.json)"

    # Parser ===========================================================================================================
    parser = ArgumentParser()
    parser.add_argument(
        "--log-timestamps",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="print timestamps in logs (default: off)",
    )

    subcommands = parser.add_subparsers(title="subcommands", dest="subcommand")

    daemon_parser = subcommands.add_parser("daemon")
    daemon_subcommands = daemon_parser.add_subparsers(title="subcommands", dest="daemon_subcommand")

    daemon_install_parser = daemon_subcommands.add_parser("install", help="install a systemd service")
    daemon_install_parser.add_argument(
        "--enable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="start the service and enable it at startup (default: on)",
    )

    watch_parser = subcommands.add_parser(
        "watch",
        help="launch a long-running process monitoring events from docker; optionally clean up according to schedule",
    )
    watch_parser.add_argument(
        "--state-file", type=UpdateOrCreateFile(encoding="utf-8"), default="state.json", help=state_file_help
    )
    add_argument_config(watch_parser)
    watch_parser.add_argument(
        "--sweep",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="while watching, perform image cleanup according to schedule (default: on)",
    )
    add_argument_verbosity(watch_parser)

    sweep_parser = subcommands.add_parser("sweep", help="perform an immediate one-time image cleanup")
    sweep_parser.add_argument(
        "--state-file", type=argparse.FileType("r", encoding="utf-8"), default="state.json", help=state_file_help
    )
    add_argument_config(sweep_parser)
    add_argument_verbosity(sweep_parser)

    return parser


def load_config(fd):
    try:
        config = config_mod.load(fd)
        logger.debug("loaded the following configuration:\n%s", config_mod.dumps(config))
        fd.close()
        return config
    except ValueError as e:
        logger.error("failed to load configuration file: %s", str(e))
        sys.exit(1)


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

        config = load_config(args.config)
        state = state_mod.load(args.state_file)

        asyncio.run(watch(config=config, state=state, state_fd=args.state_file, do_sweep=args.sweep))
    elif args.subcommand == "sweep":
        init_logging(verbose=args.verbose, timestamps=args.log_timestamps)

        config = load_config(args.config)
        state = state_mod.load(args.state_file)

        sweep(state, config.max_age)
    else:
        raise RuntimeError("unhandled subcommand")


if __name__ == "__main__":
    sys.exit(main())
