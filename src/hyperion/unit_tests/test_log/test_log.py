import os
from logging import FileHandler
from unittest.mock import MagicMock, patch

import pytest
from dodal.log import LOGGER as dodal_logger

from hyperion import log


@pytest.fixture
def clear_loggers():
    [h.close() and log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [h.close() and log.ISPYB_LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [h.close() and log.NEXUS_LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]
    mock_open_with_tell = MagicMock()
    mock_open_with_tell.tell.return_value = 0
    with (
        patch("dodal.log.logging.FileHandler._open", mock_open_with_tell),
        patch("dodal.log.GELFTCPHandler.emit") as graylog_emit,
        patch("dodal.log.logging.FileHandler.emit") as filehandler_emit,
    ):
        yield filehandler_emit, graylog_emit
    [h.close() and log.LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [h.close() and log.ISPYB_LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [h.close() and log.NEXUS_LOGGER.removeHandler(h) for h in log.LOGGER.handlers]
    [dodal_logger.removeHandler(h) for h in dodal_logger.handlers]


@pytest.mark.skip_log_setup
@patch("dodal.log.config_bluesky_logging", autospec=True)
@patch("dodal.log.config_ophyd_logging", autospec=True)
def test_no_env_variable_sets_correct_file_handler(
    mock_config_ophyd,
    mock_config_bluesky,
    clear_loggers,
) -> None:
    log.set_up_hyperion_logging_handlers(logging_level=None, dev_mode=True)
    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)  # type: ignore
    )

    assert file_handlers.baseFilename.endswith("/tmp/dev/hyperion.txt")


@pytest.mark.skip_log_setup
@patch("hyperion.log.Path.mkdir", autospec=True)
@patch.dict(
    os.environ, {"HYPERION_LOG_DIR": "./dls_sw/s03/logs/bluesky"}
)  # Note we use a relative path here so it works in CI
def test_set_env_variable_sets_correct_file_handler(
    mock_dir,
    clear_loggers,
) -> None:
    log.set_up_hyperion_logging_handlers(logging_level=None, dev_mode=False)

    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)  # type: ignore
    )

    assert file_handlers.baseFilename.endswith("/dls_sw/s03/logs/bluesky/hyperion.txt")


@pytest.mark.skip_log_setup
def test_messages_logged_from_dodal_and_hyperion_contain_dcgid(
    clear_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_loggers
    log.set_up_hyperion_logging_handlers()

    log.set_dcgid_tag(100)

    logger = log.LOGGER
    logger.info("test_hyperion")
    dodal_logger.info("test_dodal")

    filehandler_calls = mock_filehandler_emit.mock_calls[1:]
    graylog_calls = mock_GELFTCPHandler_emit.mock_calls[1:]

    for handler in [filehandler_calls, graylog_calls]:
        dc_group_id_correct = [c.args[0].dc_group_id == 100 for c in handler]
        assert all(dc_group_id_correct)


@pytest.mark.skip_log_setup
def test_messages_logged_from_dodal_and_hyperion_get_sent_to_graylog_and_file(
    clear_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_loggers
    log.set_up_hyperion_logging_handlers()
    logger = log.LOGGER
    logger.info("test_hyperion")
    dodal_logger.info("test_dodal")

    filehandler_calls = mock_filehandler_emit.mock_calls
    graylog_calls = mock_GELFTCPHandler_emit.mock_calls

    assert len(filehandler_calls) >= 2
    assert len(graylog_calls) >= 2

    for handler in [filehandler_calls, graylog_calls]:
        handler_names = [c.args[0].name for c in handler]
        handler_messages = [c.args[0].message for c in handler]
        assert "Hyperion" in handler_names
        assert "Dodal" in handler_names
        assert "test_hyperion" in handler_messages
        assert "test_dodal" in handler_messages


@pytest.mark.skip_log_setup
def test_callback_loggers_log_to_own_files(
    clear_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_loggers
    hyperion_handlers = log.set_up_hyperion_logging_handlers()

    hyperion_logger = log.LOGGER
    ispyb_logger = log.ISPYB_LOGGER
    nexus_logger = log.NEXUS_LOGGER
    log.set_up_callback_logging_handlers("ispyb", log.ISPYB_LOGGER, "INFO")
    log.set_up_callback_logging_handlers("nexus", log.NEXUS_LOGGER, "INFO")

    hyperion_logger.info("test_hyperion")
    ispyb_logger.info("test_ispyb")
    nexus_logger.info("test_nexus")

    total_filehandler_calls = mock_filehandler_emit.mock_calls
    total_graylog_calls = mock_GELFTCPHandler_emit.mock_calls

    assert len(total_filehandler_calls) == len(total_graylog_calls)

    hyperion_filehandler = hyperion_handlers[2]
    ispyb_filehandler = ispyb_logger.handlers[2]
    nexus_filehandler = nexus_logger.handlers[2]

    assert nexus_filehandler.baseFilename != hyperion_filehandler.baseFilename  # type: ignore
    assert ispyb_filehandler.baseFilename != hyperion_filehandler.baseFilename  # type: ignore
    assert ispyb_filehandler.baseFilename != nexus_filehandler.baseFilename  # type: ignore
