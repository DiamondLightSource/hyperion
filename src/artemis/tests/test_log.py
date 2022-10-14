from os import environ
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from artemis import log


@pytest.fixture()
def mock_logger():
    with patch("artemis.log.LOGGER") as mock_LOGGER:
        yield mock_LOGGER


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_handlers_set_at_correct_default_level(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    handlers = log.set_up_logging_handlers(None, False)

    for handler in handlers:
        mock_logger.addHandler.assert_any_call(handler)
        handler.setLevel.assert_called_once_with("INFO")


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_handlers_set_at_correct_debug_level(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    handlers = log.set_up_logging_handlers("DEBUG", True)

    for handler in handlers:
        mock_logger.addHandler.assert_any_call(handler)
        handler.setLevel.assert_called_once_with("DEBUG")


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_dev_mode_sets_correct_graypy_handler(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, True)
    mock_GELFTCPHandler.assert_called_once_with("localhost", 5555)


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_prod_mode_sets_correct_graypy_handler(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, False)
    mock_GELFTCPHandler.assert_called_once_with("graylog2.diamond.ac.uk", 12218)


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_dev_mode_sets_correct_file_handler(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, True)
    mock_logging.FileHandler.assert_called_once_with(
        filename=Path("./tmp/dev/artemis.txt")
    )


def do_nothing():
    pass


@patch("artemis.log.Path.mkdir")
@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
@patch.dict(environ, {"BEAMLINE": "s03"})
def test_prod_mode_sets_correct_file_handler(
    mock_logging,
    mock_GELFTCPHandler,
    mock_dir,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, False)
    mock_logging.FileHandler.assert_called_once_with(
        filename=Path("/dls_sw/s03/logs/bluesky/artemis.txt")
    )


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
def test_setting_debug_in_prod_gives_warning(
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    warning_string = (
        'STARTING ARTEMIS IN DEBUG WITHOUT "--dev" WILL FLOOD PRODUCTION '
        "GRAYLOG WITH MESSAGES. If you really need debug messages, set up a local "
        "graylog instead!\n"
    )
    log.set_up_logging_handlers("DEBUG", False)
    mock_logger.warning.assert_any_call(warning_string)
