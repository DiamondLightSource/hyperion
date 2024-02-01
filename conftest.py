from os import environ, getenv
from typing import Iterator
from unittest.mock import patch

import pytest

print("Adjusting S03 EPICS environment ...")
s03_epics_server_port = getenv("S03_EPICS_CA_SERVER_PORT")
s03_epics_repeater_port = getenv("S03_EPICS_CA_REPEATER_PORT")
if s03_epics_server_port:
    environ["EPICS_CA_SERVER_PORT"] = s03_epics_server_port
    print(f"[EPICS_CA_SERVER_PORT] = {s03_epics_server_port}")
if s03_epics_repeater_port:
    environ["EPICS_CA_REPEATER_PORT"] = s03_epics_repeater_port
    print(f"[EPICS_CA_REPEATER_PORT] = {s03_epics_repeater_port}")


def pytest_addoption(parser):
    parser.addoption(
        "--debug-logging",
        action="store_true",
        default=False,
        help="initialise test loggers in DEBUG instead of INFO",
    )


@pytest.fixture(scope="session", autouse=True)
def default_session_fixture() -> Iterator[None]:
    print("Patching bluesky 0MQ Publisher in __main__ for the whole session")
    with patch("hyperion.__main__.Publisher"):
        yield
