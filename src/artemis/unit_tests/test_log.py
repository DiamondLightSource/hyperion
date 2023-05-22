import os
from logging import FileHandler
from unittest.mock import patch

import pytest
from dodal.log import LOGGER as dodal_logger

from artemis import log


@pytest.fixture
def clear_loggers():
    [log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]
    with (
        patch("dodal.log.logging.FileHandler._open"),
        patch("dodal.log.GELFTCPHandler.emit") as graylog_emit,
        patch("dodal.log.logging.FileHandler.emit") as filehandler_emit,
    ):
        yield filehandler_emit, graylog_emit
    [log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]


@pytest.mark.skip(reason="to be fixed in #644")
@patch("dodal.log.config_bluesky_logging")
@patch("dodal.log.config_ophyd_logging")
def test_no_env_variable_sets_correct_file_handler(
    mock_config_ophyd,
    mock_config_bluesky,
    clear_loggers,
):
    log.set_up_logging_handlers(None, True)
    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)
    )

    assert file_handlers.baseFilename.endswith("/tmp/dev/artemis.txt")


@pytest.mark.skip(reason="to be fixed in #644")
@patch("artemis.log.Path.mkdir")
@patch.dict(
    os.environ, {"ARTEMIS_LOG_DIR": "./dls_sw/s03/logs/bluesky"}
)  # Note we use a relative path here so it works in CI
def test_set_env_variable_sets_correct_file_handler(
    mock_dir,
    clear_loggers,
):
    log.set_up_logging_handlers(None, False)

    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)
    )

    assert file_handlers.baseFilename.endswith("/dls_sw/s03/logs/bluesky/artemis.txt")


@pytest.mark.skip(reason="to be fixed in #644")
def test_messages_logged_from_dodal_and_artemis_contain_dcgid(
    clear_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_loggers
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


def test_messages_logged_from_dodal_and_artemis_get_sent_to_graylog_and_file(
    clear_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_loggers
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
