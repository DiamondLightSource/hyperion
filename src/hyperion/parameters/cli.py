import argparse

from pydantic.dataclasses import dataclass


@dataclass
class HyperionArgs:
    dev_mode: bool = False
    use_external_callbacks: bool = False
    verbose_event_logging: bool = False
    skip_startup_connection: bool = False


def _add_callback_relevant_args(parser: argparse.ArgumentParser) -> None:
    """adds arguments relevant to hyperion-callbacks."""
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use dev options, such as local graylog instances and S03",
    )


def parse_callback_dev_mode_arg() -> bool:
    """Returns the bool representing the 'dev_mode' argument."""
    parser = argparse.ArgumentParser()
    _add_callback_relevant_args(parser)
    args = parser.parse_args()
    return args.dev


def parse_cli_args() -> HyperionArgs:
    """Parses all arguments relevant to hyperion. Returns an HyperionArgs dataclass with
    the fields: (verbose_event_logging: bool,
                 dev_mode: bool,
                 skip_startup_connection: bool,
                 external_callbacks: bool)"""
    parser = argparse.ArgumentParser()
    _add_callback_relevant_args(parser)
    parser.add_argument(
        "--verbose-event-logging",
        action="store_true",
        help="Log all bluesky event documents to graylog",
    )
    parser.add_argument(
        "--skip-startup-connection",
        action="store_true",
        help="Skip connecting to EPICS PVs on startup",
    )
    parser.add_argument(
        "--external-callbacks",
        action="store_true",
        help="Run the external hyperion-callbacks service and publish events over ZMQ",
    )
    args = parser.parse_args()
    return HyperionArgs(
        verbose_event_logging=args.verbose_event_logging or False,
        dev_mode=args.dev or False,
        skip_startup_connection=args.skip_startup_connection or False,
        use_external_callbacks=args.external_callbacks or False,
    )
