import sys


def pytest_runtest_teardown():
    if "dodal.i03" in sys.modules:
        sys.modules["dodal.i03"].clear_devices()
