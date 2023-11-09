from dodal.log import LOGGER

from hyperion.conftest import _destroy_loggers
from hyperion.log import ALL_LOGGERS


def pytest_runtest_setup():
    _destroy_loggers([*ALL_LOGGERS, LOGGER])


def pytest_runtest_teardown():
    _destroy_loggers([*ALL_LOGGERS, LOGGER])
