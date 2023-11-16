import sys
from os import environ, getenv

import pytest
from dodal.log import LOGGER as dodal_logger

from hyperion.log import (
    ALL_LOGGERS,
    ISPYB_LOGGER,
    LOGGER,
    NEXUS_LOGGER,
    set_up_logging_handlers,
)
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def _destroy_loggers(loggers):
    for logger in loggers:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()


def pytest_runtest_setup(item):
    markers = [m.name for m in item.own_markers]
    log_level = "DEBUG" if item.config.option.debug_logging else "INFO"
    log_params = {"logging_level": log_level, "dev_mode": True}
    if "skip_log_setup" not in markers:
        if LOGGER.handlers == []:
            if dodal_logger.handlers == []:
                print(f"Initialising Hyperion logger for tests at {log_level}")
                set_up_logging_handlers(logger=LOGGER, **log_params)
        if ISPYB_LOGGER.handlers == []:
            print(f"Initialising ISPyB logger for tests at {log_level}")
            set_up_logging_handlers(
                **log_params,
                filename="hyperion_ispyb_callback.txt",
                logger=ISPYB_LOGGER,
            )
        if NEXUS_LOGGER.handlers == []:
            print(f"Initialising nexus logger for tests at {log_level}")
            set_up_logging_handlers(
                **log_params,
                filename="hyperion_nexus_callback.txt",
                logger=NEXUS_LOGGER,
            )
    else:
        print("Skipping log setup for log test - deleting existing handlers")
        _destroy_loggers([*ALL_LOGGERS, dodal_logger])


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


@pytest.fixture
def dummy_external_gridscan_params():
    external = ExternalParameters.parse_file(
        "src/hyperion/parameters/tests/test_data/external_param_test_gridscan.json"
    )
    external.experiment_type = "flyscan_xray_centre"
    return external


@pytest.fixture
def dummy_gridscan_params(dummy_external_gridscan_params):
    return GridscanInternalParameters.from_external(dummy_external_gridscan_params)


@pytest.fixture
def dummy_rotation_external_params():
    external = ExternalParameters.parse_file(
        "src/hyperion/parameters/tests/test_data/external_param_test_gridscan.json"
    )
    external.experiment_type = "rotation_scan"
    return external


@pytest.fixture
def dummy_rotation_params(dummy_rotation_external_params):
    return GridscanInternalParameters.from_external(dummy_rotation_external_params)
