from dodal.log import LOGGER

from hyperion.log import ALL_LOGGERS

from ....conftest import _destroy_loggers


def pytest_runtest_setup():
    _destroy_loggers([*ALL_LOGGERS, LOGGER])


def pytest_runtest_teardown():
    _destroy_loggers([*ALL_LOGGERS, LOGGER])
