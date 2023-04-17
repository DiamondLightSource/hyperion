import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from artemis import log


@pytest.fixture()
def mock_logger():
    with patch("artemis.log.LOGGER") as mock_LOGGER:
        yield mock_LOGGER
        log.beamline = None


@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
@patch("artemis.log.EnhancedRollingFileHandler")
def test_handlers_set_at_correct_default_level(
    mock_enhanced_log,
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
@patch("artemis.log.EnhancedRollingFileHandler")
def test_handlers_set_at_correct_debug_level(
    mock_enhanced_log,
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
@patch("artemis.log.EnhancedRollingFileHandler")
def test_no_env_variable_sets_correct_file_handler(
    mock_enhanced_log,
    mock_logging,
    mock_GELFTCPHandler,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, True)
    mock_enhanced_log.assert_called_once_with(
        filename=Path("./tmp/dev/artemis.txt"),
        when="D",
        interval=1,
        backupCount=10,
        maxBytes=1e8,
    )


@patch("artemis.log.Path.mkdir")
@patch("artemis.log.GELFTCPHandler")
@patch("artemis.log.logging")
@patch("artemis.log.EnhancedRollingFileHandler")
@patch.dict(os.environ, {"ARTEMIS_LOG_DIR": "/dls_sw/s03/logs/bluesky"})
def test_set_env_variable_sets_correct_file_handler(
    mock_enhanced_log,
    mock_logging,
    mock_GELFTCPHandler,
    mock_dir,
    mock_logger: MagicMock,
):
    log.set_up_logging_handlers(None, False)
    mock_enhanced_log.assert_called_once_with(
        filename=Path("/dls_sw/s03/logs/bluesky/artemis.txt"),
        when="D",
        interval=1,
        backupCount=10,
        maxBytes=1e8,
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


def test_beamline_filter_adds_dev_if_no_beamline():
    filter = log.BeamlineFilter()
    record = MagicMock()
    assert filter.filter(record)
    assert record.beamline == "dev"


def test_given_delay_set_when_do_rollover_then_stream_created():
    my_handler = log.EnhancedRollingFileHandler(filename="", delay=True, maxBytes=0)
    my_handler._open = MagicMock()
    my_handler.shouldRollover(MagicMock())
    my_handler._open.assert_called_once()


def test_rollover_on_maxBytes():
    my_handler = log.EnhancedRollingFileHandler(
        filename="test_log.txt", delay=False, maxBytes=1000
    )
    my_handler.stream.tell = MagicMock()
    my_handler.stream.tell.return_value = 900
    my_handler.doRollover = MagicMock()
    LOGGER = logging.getLogger("Artemis")
    LOGGER.addHandler(my_handler)
    LOGGER.info("test")
    my_handler.doRollover.assert_not_called()  # Log file isn't 1000 bytes big yet
    string_to_get_over_max_bytes = ""
    for i in range(100):
        string_to_get_over_max_bytes += "test"
    LOGGER.info(string_to_get_over_max_bytes)
    my_handler.doRollover.assert_called_once()
    os.remove("test_log.txt")
