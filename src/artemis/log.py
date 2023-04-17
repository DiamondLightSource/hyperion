import logging
import logging.handlers
from os import environ
from pathlib import Path
from typing import List, Optional, Tuple, Union

from bluesky.log import config_bluesky_logging
from bluesky.log import logger as bluesky_logger
from graypy import GELFTCPHandler
from ophyd.log import config_ophyd_logging
from ophyd.log import logger as ophyd_logger

beamline: Union[str, None] = environ.get("BEAMLINE")
LOGGER = logging.getLogger("Artemis")
LOGGER.setLevel(logging.DEBUG)  # default logger to log everything
ophyd_logger.parent = LOGGER
bluesky_logger.parent = LOGGER


class EnhancedRollingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Combines features of TimedRotatingFileHandler and RotatingFileHandler"""

    def __init__(
        self,
        filename,
        when="D",
        interval=1,
        backupCount=10,
        encoding=None,
        delay=0,
        utc=0,
        maxBytes=1e8,
    ):
        logging.handlers.TimedRotatingFileHandler.__init__(
            self, filename, when, interval, backupCount, encoding, delay, utc
        )
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        """
        Check file size and times to see if rollover should occur
        """
        time = super().shouldRollover(record)
        if time:
            return 1
        else:
            if self.stream is None:  # delay was set...
                self.stream = self._open()
            if self.maxBytes > 0:  # are we rolling over?
                msg = "%s\n" % self.format(record)
                self.stream.seek(0, 2)  # due to non-posix-compliant Windows feature
                if self.stream.tell() + len(msg) >= self.maxBytes:
                    return 1
        return 0

    def getFilesToDelete(self):
        """
        Override method to do nothing - we don't want logs to be deleted
        """
        return []


class BeamlineFilter(logging.Filter):
    def filter(self, record):
        record.beamline = beamline if beamline else "dev"
        return True


class DCGIDFilter(logging.Filter):
    dc_group_id: Optional[str] = None

    def filter(self, record):
        if self.dc_group_id:
            record.dc_group_id = self.dc_group_id
        return True


dc_group_id_filter = DCGIDFilter()


def set_dcgid_tag(dcgid):
    """Set the datacollection group id as a tag on all subsequent log messages.
    Setting to None will remove the tag."""
    dc_group_id_filter.dc_group_id = dcgid


def set_up_logging_handlers(
    logging_level: Union[str, None] = "INFO", dev_mode: bool = False
) -> List[logging.Handler]:
    """Set up the logging level and instances for user chosen level of logging.

    Mode defaults to production and can be switched to dev with the --dev flag on run.
    """
    logging_level = logging_level if logging_level else "INFO"
    file_path = Path(_get_logging_file_path(), "artemis.txt")
    graylog_host, graylog_port = _get_graylog_configuration(dev_mode)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s %(module)s %(levelname)s: %(message)s"
    )
    handlers: list[logging.Handler] = [
        GELFTCPHandler(graylog_host, graylog_port),
        logging.StreamHandler(),
        EnhancedRollingFileHandler(
            filename=file_path,
            when="D",
            interval=1,
            backupCount=10,
            maxBytes=1e8,
        ),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(logging_level)
        LOGGER.addHandler(handler)

    LOGGER.addFilter(BeamlineFilter())
    LOGGER.addFilter(dc_group_id_filter)

    # for assistance in debugging
    if dev_mode:
        set_seperate_ophyd_bluesky_files(
            logging_level=logging_level, logging_path=_get_logging_file_path()
        )

    # Warn users if trying to run in prod in debug mode
    if not dev_mode and logging_level == "DEBUG":
        LOGGER.warning(
            'STARTING ARTEMIS IN DEBUG WITHOUT "--dev" WILL FLOOD PRODUCTION GRAYLOG'
            " WITH MESSAGES. If you really need debug messages, set up a"
            " local graylog instead!\n"
        )

    return handlers


def _get_graylog_configuration(dev_mode: bool) -> Tuple[str, int]:
    """Get the host and port for the  graylog interaction.

    If running on dev mode, this switches to localhost. Otherwise it publishes to the
    dls graylog.

    Returns:
        (host,port): A tuple of the relevent host and port for graylog.
    """
    if dev_mode:
        return "localhost", 5555
    else:
        return "graylog2.diamond.ac.uk", 12218


def _get_logging_file_path() -> Path:
    """Get the path to write the artemis log files to.

    If the ARTEMIS_LOG_DIR environment variable exists then logs will be put in here.

    If no envrionment variable is found it will default it to the tmp/dev directory.

    Returns:
        logging_path (Path): Path to the log file for the file handler to write to.
    """
    logging_path: Path

    artemis_log_dir = environ.get("ARTEMIS_LOG_DIR")
    if artemis_log_dir:
        logging_path = Path(artemis_log_dir)
    else:
        logging_path = Path("./tmp/dev/")

    Path(logging_path).mkdir(parents=True, exist_ok=True)
    return logging_path


def set_seperate_ophyd_bluesky_files(logging_level: str, logging_path: Path) -> None:
    """Set file path for the file handlder to the individual Bluesky and Ophyd loggers.

    These provide seperate, nicely formatted logs in the same dir as the artemis log
    file for each individual module.
    """
    bluesky_file_path: Path = Path(logging_path, "bluesky.log")
    ophyd_file_path: Path = Path(logging_path, "ophyd.log")

    config_bluesky_logging(file=str(bluesky_file_path), level=logging_level)
    config_ophyd_logging(file=str(ophyd_file_path), level=logging_level)
