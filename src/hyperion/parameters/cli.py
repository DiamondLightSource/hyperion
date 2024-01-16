import argparse

from pydantic.dataclasses import dataclass


@dataclass
class CallbackArgs:
    logging_level: str
    dev_mode: bool


@dataclass
class HyperionArgs:
    logging_level: str
    dev_mode: bool
    use_external_callbacks: bool
    verbose_event_logging: bool
    skip_startup_connection: bool


def add_callback_relevant_args(parser: argparse.ArgumentParser) -> None:
    """adds arguments relevant to hyperion-callbacks. Returns the tuple: (log_level: str, dev_mode: bool)"""
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use dev options, such as local graylog instances and S03",
    )
    parser.add_argument(
        "--logging-level",
        type=str,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Choose overall logging level, defaults to INFO",
    )


def parse_callback_cli_args() -> CallbackArgs:
    parser = argparse.ArgumentParser()
    add_callback_relevant_args(parser)
    args = parser.parse_args()
    return CallbackArgs(logging_level=args.logging_level, dev_mode=args.dev)


def parse_cli_args() -> HyperionArgs:
    """Parses all arguments relevant to hyperion. Returns the tuple: (log_level: str, verbose_event_logging: bool, dev_mode: bool, skip_startup_connection: bool )"""
    parser = argparse.ArgumentParser()
    add_callback_relevant_args(parser)
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
        "--external_callbacks",
        action="store_true",
        help="Run the external hyperion-callbacks service and publish events over ZMQ",
    )
    args = parser.parse_args()
    return HyperionArgs(
        logging_level=args.logging_level,
        verbose_event_logging=args.verbose_event_logging,
        dev_mode=args.dev,
        skip_startup_connection=args.skip_startup_connection,
        use_external_callbacks=args.external_callbacks,
    )
