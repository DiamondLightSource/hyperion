from dodal.log import LOGGER

from hyperion.log import ALL_LOGGERS

from ....conftest import _reset_loggers


def pytest_runtest_setup():
    _reset_loggers([*ALL_LOGGERS, LOGGER])


def pytest_runtest_teardown():
    _reset_loggers([*ALL_LOGGERS, LOGGER])
