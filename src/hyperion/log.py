import logging
from os import environ
from pathlib import Path
from typing import Optional
from uuid import uuid4

from dodal.log import (
    ERROR_LOG_BUFFER_LINES,
    integrate_bluesky_and_ophyd_logging,
    set_up_all_logging_handlers,
)
from dodal.log import LOGGER as dodal_logger

LOGGER = logging.getLogger("Hyperion")
LOGGER.setLevel("DEBUG")
LOGGER.parent = dodal_logger

ISPYB_LOGGER = logging.getLogger("Hyperion ISPyB and Zocalo callbacks")
ISPYB_LOGGER.setLevel(logging.DEBUG)

NEXUS_LOGGER = logging.getLogger("Hyperion NeXus callbacks")
NEXUS_LOGGER.setLevel(logging.DEBUG)

ALL_LOGGERS = [LOGGER, ISPYB_LOGGER, NEXUS_LOGGER]


class DCGIDFilter(logging.Filter):
    dc_group_id: Optional[str] = None

    def filter(self, record):
        if self.dc_group_id:
            record.dc_group_id = self.dc_group_id
        return True


class RunUIDFilter(logging.Filter):
    run_uid: Optional[str] = None

    def filter(self, record):
        if self.run_uid:
            record.run_uid = self.run_uid
        return True

    def create_and_set_new(self) -> str:
        self.run_uid = str(uuid4())
        return self.run_uid


dc_group_id_filter = DCGIDFilter()
run_uid_filter = RunUIDFilter()


def set_dcgid_tag(dcgid):
    """Set the datacollection group id as a tag on all subsequent log messages.
    Setting to None will remove the tag."""
    dc_group_id_filter.dc_group_id = dcgid


def do_default_logging_setup(dev_mode=False):
    handlers = set_up_all_logging_handlers(
        dodal_logger,
        _get_logging_dir(),
        "hyperion.log",
        dev_mode,
        ERROR_LOG_BUFFER_LINES,
    )
    integrate_bluesky_and_ophyd_logging(dodal_logger, handlers)
    handlers["graylog_handler"].addFilter(dc_group_id_filter)
    handlers["graylog_handler"].addFilter(dc_group_id_filter)


def _get_logging_dir() -> Path:
    """Get the path to write the hyperion log files to.

    If the HYPERION_LOG_DIR environment variable exists then logs will be put in here.
    If no environment variable is found it will default it to the ./tmp/dev directory.

    Returns:
        logging_path (Path): Path to the log file for the file handler to write to.
    """
    logging_path = Path(environ.get("HYPERION_LOG_DIR") or "./tmp/dev/")
    return logging_path
