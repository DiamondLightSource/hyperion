import sys
from os import environ, getenv


def pytest_runtest_teardown():
    if "dodal.beamline_utils" in sys.modules:
        sys.modules["dodal.beamline_utils"].clear_devices()
    if "artemis.log" in sys.modules:
        artemis_log = sys.modules["artemis.log"]
        [artemis_log.LOGGER.removeHandler(h) for h in artemis_log.LOGGER.handlers]
    if "dodal.log" in sys.modules:
        dodal_log = sys.modules["dodal.log"]
        [dodal_log.LOGGER.removeHandler(h) for h in dodal_log.LOGGER.handlers]


s03_epics_server_port = getenv("S03_EPICS_CA_SERVER_PORT")
s03_epics_repeater_port = getenv("S03_EPICS_CA_REPEATER_PORT")

if s03_epics_server_port is not None:
    environ["EPICS_CA_SERVER_PORT"] = s03_epics_server_port
    print(f"[EPICS_CA_SERVER_PORT] = {s03_epics_server_port}")
if s03_epics_repeater_port is not None:
    environ["EPICS_CA_REPEATER_PORT"] = s03_epics_repeater_port
    print(f"[EPICS_CA_REPEATER_PORT] = {s03_epics_repeater_port}")
