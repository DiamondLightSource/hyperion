from typing import Iterator
from unittest.mock import patch

import pytest


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
