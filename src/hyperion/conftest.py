import sys
from os import environ, getenv

from hyperion.log import (
    ISPYB_LOGGER,
    LOGGER,
    NEXUS_LOGGER,
    set_up_callback_logging_handlers,
    set_up_hyperion_logging_handlers,
)


def pytest_runtest_setup(item):
    markers = [m.name for m in item.own_markers]
    log_level = "DEBUG" if item.config.option.debug_logging else "INFO"
    if "skip_log_setup" not in markers:
        print(f"Initialising loggers for tests at {log_level}")
        if LOGGER.handlers == []:
            set_up_hyperion_logging_handlers(LOGGER, log_level, True)
        if ISPYB_LOGGER.handlers == []:
            set_up_callback_logging_handlers(
                "hyperion_ispyb_callback.txt", ISPYB_LOGGER, log_level, True
            )
        if NEXUS_LOGGER.handlers == []:
            set_up_callback_logging_handlers(
                "hyperion_nexus_callback.txt", NEXUS_LOGGER, log_level, True
            )
    else:
        print("Skipping log setup for log test - deleting existing handlers")
        LOGGER.handlers.clear()
        ISPYB_LOGGER.handlers.clear()
        NEXUS_LOGGER.handlers.clear()
        LOGGER.handlers = []
        NEXUS_LOGGER.handlers = []
        ISPYB_LOGGER.handlers = []


def pytest_runtest_teardown():
    if "dodal.beamlines.beamline_utils" in sys.modules:
        sys.modules["dodal.beamlines.beamline_utils"].clear_devices()


s03_epics_server_port = getenv("S03_EPICS_CA_SERVER_PORT")
s03_epics_repeater_port = getenv("S03_EPICS_CA_REPEATER_PORT")

if s03_epics_server_port is not None:
    environ["EPICS_CA_SERVER_PORT"] = s03_epics_server_port
    print(f"[EPICS_CA_SERVER_PORT] = {s03_epics_server_port}")
if s03_epics_repeater_port is not None:
    environ["EPICS_CA_REPEATER_PORT"] = s03_epics_repeater_port
    print(f"[EPICS_CA_REPEATER_PORT] = {s03_epics_repeater_port}")
