import argparse


def parse_callback_relevant_args(parser=argparse.ArgumentParser()) -> tuple[str, bool]:
    """Parses arguments relevant to hyperion-callbacks. Returns the tuple: (log_level: str, dev_mode: bool)"""
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
    args = parser.parse_args()
    return (args.logging_level, args.dev)


def parse_cli_args() -> tuple[str | None, bool, bool, bool]:
    """Parses all arguments relevant to hyperion. Returns the tuple: (log_level: str, verbose_event_logging: bool, dev_mode: bool, skip_startup_connection: bool )"""
    parser = argparse.ArgumentParser()
    parse_callback_relevant_args(parser)
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
    args = parser.parse_args()
    return (
        args.logging_level,
        args.verbose_event_logging,
        args.dev,
        args.skip_startup_connection,
    )
