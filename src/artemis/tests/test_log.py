import os
from pathlib import Path
from unittest.mock import patch

from artemis.log import LOGGER, set_up_logging


@patch("artemis.log.graypy")
@patch("artemis.log.logging")
def test_handlers_set_at_correct_debug_level(mock_logging, mock_graypy):
    set_up_logging(None, False)
    handlers = LOGGER.handlers
    assert len(handlers) == 3
    for handler in handlers:
        handler.setLevel.assert_called_once_with("INFO")


@patch("artemis.log.graypy")
@patch("artemis.log.logging")
def test_dev_mode_sets_correct_graypy_handler(mock_logging, mock_graypy):
    set_up_logging(None, True)
    mock_graypy.GELFTCPHandler.assert_called_once_with("localhost", 5555)


@patch("artemis.log.graypy")
@patch("artemis.log.logging")
def test_prod_mode_sets_correct_graypy_handler(mock_logging, mock_graypy):
    set_up_logging(None, False)
    mock_graypy.GELFTCPHandler.assert_called_once_with("graylog2.diamond.ac.uk", 12218)


@patch("artemis.log.graypy")
@patch("artemis.log.logging")
def test_dev_mode_sets_correct_file_handler(mock_logging, mock_graypy):
    set_up_logging(None, True)
    mock_logging.FileHandler.assert_called_once_with(
        filename=Path("./tmp/dev/artemis.txt")
    )


@patch("artemis.log.graypy")
@patch("artemis.log.logging")
@patch.dict(os.environ, {"BEAMLINE": "S03"})
def test_prod_mode_sets_correct_file_handler(mock_logging, mock_graypy):
    set_up_logging(None, False)
    mock_logging.FileHandler.assert_called_once_with(
        filename=Path("/dls_sw/S03/logs/bluesky/artemis.txt")
    )
