import logging
from logging.handlers import TimedRotatingFileHandler
from os import environ
from pathlib import Path
from typing import Optional

from dodal.log import (
    ERROR_LOG_BUFFER_LINES,
    CircularMemoryHandler,
    DodalLogHandlers,
    integrate_bluesky_and_ophyd_logging,
    set_up_all_logging_handlers,
)
from dodal.log import LOGGER as dodal_logger

from hyperion.parameters.constants import CONST

LOGGER = logging.getLogger("Hyperion")
LOGGER.setLevel("DEBUG")
LOGGER.parent = dodal_logger
__logger_handlers: Optional[DodalLogHandlers] = None

ISPYB_LOGGER = logging.getLogger("Hyperion ISPyB and Zocalo callbacks")
ISPYB_LOGGER.setLevel(logging.DEBUG)

NEXUS_LOGGER = logging.getLogger("Hyperion NeXus callbacks")
NEXUS_LOGGER.setLevel(logging.DEBUG)

ALL_LOGGERS = [LOGGER, ISPYB_LOGGER, NEXUS_LOGGER]


class ExperimentMetadataTagFilter(logging.Filter):
    dc_group_id: Optional[str] = None
    run_uid: Optional[str] = None

    def filter(self, record):
        if self.dc_group_id:
            record.dc_group_id = self.dc_group_id
        if self.run_uid:
            record.run_uid = self.run_uid
        return True


tag_filter = ExperimentMetadataTagFilter()


def set_dcgid_tag(dcgid):
    """Set the datacollection group id as a tag on all subsequent log messages.
    Setting to None will remove the tag."""
    tag_filter.dc_group_id = dcgid


def set_uid_tag(uid):
    tag_filter.run_uid = uid


def do_default_logging_setup(dev_mode=False):
    handlers = set_up_all_logging_handlers(
        dodal_logger,
        _get_logging_dir(),
        "hyperion.log",
        dev_mode,
        ERROR_LOG_BUFFER_LINES,
        CONST.GRAYLOG_PORT,
    )
    integrate_bluesky_and_ophyd_logging(dodal_logger)
    handlers["graylog_handler"].addFilter(tag_filter)

    global __logger_handlers
    __logger_handlers = handlers


def _get_debug_handler() -> CircularMemoryHandler:
    assert (
        __logger_handlers is not None
    ), "You can only use this after running the default logging setup"
    return __logger_handlers["debug_memory_handler"]


def flush_debug_handler() -> str:
    """Writes the contents of the circular debug log buffer to disk and returns the written filename"""
    handler = _get_debug_handler()
    assert isinstance(
        handler.target, TimedRotatingFileHandler
    ), "Circular memory handler doesn't have an appropriate fileHandler target"
    handler.flush()
    return handler.target.baseFilename


def _get_logging_dir() -> Path:
    """Get the path to write the hyperion log files to.

    If the HYPERION_LOG_DIR environment variable exists then logs will be put in here.
    If no environment variable is found it will default it to the ./tmp/dev directory.

    Returns:
        logging_path (Path): Path to the log file for the file handler to write to.
    """
    logging_path = Path(environ.get("HYPERION_LOG_DIR") or "./tmp/dev/")
    return logging_path
