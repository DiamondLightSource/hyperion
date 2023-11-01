import sys


def pytest_runtest_setup():
    if "hyperion.log" in sys.modules:
        hyperion_log = sys.modules["hyperion.log"]
        [h.close() for h in hyperion_log.LOGGER.handlers]
        [hyperion_log.LOGGER.removeHandler(h) for h in hyperion_log.LOGGER.handlers]
    if "dodal.log" in sys.modules:
        dodal_log = sys.modules["dodal.log"]
        [h.close() for h in dodal_log.LOGGER.handlers]
        [dodal_log.LOGGER.removeHandler(h) for h in dodal_log.LOGGER.handlers]


def pytest_runtest_teardown():
    if "hyperion.log" in sys.modules:
        hyperion_log = sys.modules["hyperion.log"]
        [h.close() for h in hyperion_log.LOGGER.handlers]
        [hyperion_log.LOGGER.removeHandler(h) for h in hyperion_log.LOGGER.handlers]
    if "dodal.log" in sys.modules:
        dodal_log = sys.modules["dodal.log"]
        [h.close() for h in dodal_log.LOGGER.handlers]
        [dodal_log.LOGGER.removeHandler(h) for h in dodal_log.LOGGER.handlers]
