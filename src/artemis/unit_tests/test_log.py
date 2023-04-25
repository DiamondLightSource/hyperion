import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dodal.log import LOGGER as dodal_logger

from artemis import log


@pytest.fixture
def clear_loggers():
    [log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]
    yield
    [log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]


@patch("dodal.log.config_bluesky_logging")
@patch("dodal.log.config_ophyd_logging")
@patch("dodal.log.GELFTCPHandler")
@patch("dodal.log.logging.FileHandler")
def test_no_env_variable_sets_correct_file_handler(
    mock_FileHandler,
    mock_GELFTCPHandler,
    mock_config_ophyd,
    mock_config_bluesky,
    clear_loggers,
):
    log.set_up_logging_handlers(None, True)
    mock_FileHandler.assert_called_once_with(filename=Path("./tmp/dev/artemis.txt"))


@patch("artemis.log.Path.mkdir")
@patch("dodal.log.GELFTCPHandler")
@patch("dodal.log.logging.FileHandler")
@patch.dict(os.environ, {"ARTEMIS_LOG_DIR": "/dls_sw/s03/logs/bluesky"})
def test_set_env_variable_sets_correct_file_handler(
    mock_FileHandler, mock_GELFTCPHandler, mock_dir, clear_loggers
):
    log.set_up_logging_handlers(None, False)
    mock_FileHandler.assert_called_once_with(
        filename=Path("/dls_sw/s03/logs/bluesky/artemis.txt")
    )


@patch("dodal.log.GELFTCPHandler.emit")
@patch("dodal.log.logging.FileHandler.emit")
def test_messages_logged_from_dodal_and_artemis_contain_dcgid(
    mock_filehandler_emit: MagicMock,
    mock_GELFTCPHandler_emit: MagicMock,
    clear_loggers,
):
    log.set_up_logging_handlers()

    log.set_dcgid_tag(100)

    logger = log.LOGGER
    logger.info("test_artemis")
    dodal_logger.info("test_dodal")

    filehandler_calls = mock_filehandler_emit.mock_calls
    graylog_calls = mock_GELFTCPHandler_emit.mock_calls

    for handler in [filehandler_calls, graylog_calls]:
        dc_group_id_correct = [c.args[0].dc_group_id == 100 for c in handler]
        assert all(dc_group_id_correct)


@patch("dodal.log.GELFTCPHandler.emit")
@patch("dodal.log.logging.FileHandler.emit")
def test_messages_logged_from_dodal_and_artemis_get_sent_to_graylog_and_file(
    mock_filehandler_emit: MagicMock,
    mock_GELFTCPHandler_emit: MagicMock,
    clear_loggers,
):
    log.set_up_logging_handlers()
    logger = log.LOGGER
    logger.info("test_artemis")
    dodal_logger.info("test_dodal")

    filehandler_calls = mock_filehandler_emit.mock_calls
    graylog_calls = mock_GELFTCPHandler_emit.mock_calls

    assert len(filehandler_calls) >= 2
    assert len(graylog_calls) >= 2

    for handler in [filehandler_calls, graylog_calls]:
        handler_names = [c.args[0].name for c in handler]
        handler_messages = [c.args[0].message for c in handler]
        assert "Artemis" in handler_names
        assert "Dodal" in handler_names
        assert "test_artemis" in handler_messages
        assert "test_dodal" in handler_messages
