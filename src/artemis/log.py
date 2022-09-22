import logging
from os import environ
from pathlib import Path
from typing import Tuple, Union

from bluesky.log import config_bluesky_logging
from bluesky.log import logger as bluesky_logger
from graypy import GELFTCPHandler
from ophyd.log import config_ophyd_logging
from ophyd.log import logger as ophyd_logger

LOGGER = logging.getLogger("Artemis")
LOGGER.setLevel(logging.DEBUG)  # default logger to log everything
ophyd_logger.parent = LOGGER
bluesky_logger.parent = LOGGER


def set_up_logging(logging_level: str = "INFO", dev_mode: bool = False) -> None:
    """Set up the logging level and instances for user chosen level of logging.

    Mode defaults to production and can be switched to dev with the --dev flag on run.
    """
    file_path = Path(_get_logging_file_path(), "artemis.txt")
    graylog_host, graylog_port = _get_graylog_configuration(dev_mode)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s %(module)s %(levelname)s: %(message)s"
    )
    handlers: dict[str, logging.Handler] = {
        "graylog": GELFTCPHandler(graylog_host, graylog_port),
        "stream": logging.StreamHandler(),
        "file": logging.FileHandler(filename=file_path),
    }
    for handler in handlers.values():
        handler.setFormatter(formatter)
        handler.setLevel(logging_level)
        LOGGER.addHandler(handler)

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

    If on a beamline, this will be written to the according area depending on the
    BEAMLINE envrionment variable. If no envrionment variable is found it will default
    it to the tmp/dev directory.

    Returns:
        logging_path (Path): Path to the log file for the file handler to write to.
    """
    beamline: Union[str, None] = environ.get("BEAMLINE")
    logging_path: Path

    if beamline:
        logging_path = Path("/dls_sw/" + beamline + "/logs/bluesky/")
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
