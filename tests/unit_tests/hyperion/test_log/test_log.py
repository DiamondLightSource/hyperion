import os
from logging import FileHandler
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import MagicMock, patch

import pytest
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from dodal.log import LOGGER as dodal_logger
from dodal.log import set_up_all_logging_handlers

from hyperion import log
from hyperion.external_interaction.callbacks.log_uid_tag_callback import (
    LogUidTaggingCallback,
)
from hyperion.parameters.constants import SET_LOG_UID_TAG

from .conftest import _destroy_loggers


@pytest.fixture(scope="function")
def clear_and_mock_loggers():
    _destroy_loggers([*log.ALL_LOGGERS, dodal_logger])
    mock_open_with_tell = MagicMock()
    mock_open_with_tell.tell.return_value = 0
    with (
        patch("dodal.log.logging.FileHandler._open", mock_open_with_tell),
        patch("dodal.log.GELFTCPHandler.emit") as graylog_emit,
        patch("dodal.log.TimedRotatingFileHandler.emit") as filehandler_emit,
    ):
        graylog_emit.reset_mock()
        filehandler_emit.reset_mock()
        yield filehandler_emit, graylog_emit
    _destroy_loggers([*log.ALL_LOGGERS, dodal_logger])


@pytest.mark.skip_log_setup
def test_no_env_variable_sets_correct_file_handler(
    clear_and_mock_loggers,
) -> None:
    log.do_default_logging_setup(dev_mode=True)
    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)  # type: ignore
    )

    assert file_handlers.baseFilename.endswith("/tmp/dev/hyperion.log")


@pytest.mark.skip_log_setup
@patch("dodal.log.Path.mkdir", autospec=True)
@patch.dict(
    os.environ, {"HYPERION_LOG_DIR": "./dls_sw/s03/logs/bluesky"}
)  # Note we use a relative path here so it works in CI
def test_set_env_variable_sets_correct_file_handler(
    mock_dir,
    clear_and_mock_loggers,
) -> None:
    log.do_default_logging_setup(dev_mode=True)

    file_handlers: FileHandler = next(
        filter(lambda h: isinstance(h, FileHandler), dodal_logger.handlers)  # type: ignore
    )

    assert file_handlers.baseFilename.endswith("/dls_sw/s03/logs/bluesky/hyperion.log")


@pytest.mark.skip_log_setup
def test_messages_logged_from_dodal_and_hyperion_contain_dcgid(
    clear_and_mock_loggers,
):
    _, mock_GELFTCPHandler_emit = clear_and_mock_loggers
    log.do_default_logging_setup(dev_mode=True)

    log.set_dcgid_tag(100)

    logger = log.LOGGER
    logger.info("test_hyperion")
    dodal_logger.info("test_dodal")

    graylog_calls = mock_GELFTCPHandler_emit.mock_calls[1:]

    dc_group_id_correct = [c.args[0].dc_group_id == 100 for c in graylog_calls]
    assert all(dc_group_id_correct)


@pytest.mark.skip_log_setup
def test_messages_are_tagged_with_run_uid(clear_and_mock_loggers, RE):
    _, mock_GELFTCPHandler_emit = clear_and_mock_loggers
    log.do_default_logging_setup(dev_mode=True)

    RE.subscribe(LogUidTaggingCallback())
    test_run_uid = None
    logger = log.LOGGER

    @bpp.run_decorator(
        md={
            SET_LOG_UID_TAG: True,
        }
    )
    def test_plan():
        yield from bps.sleep(0)
        assert log.run_uid_filter.run_uid is not None
        nonlocal test_run_uid
        test_run_uid = log.run_uid_filter.run_uid
        logger.info("test_hyperion")
        logger.info("test_hyperion")
        yield from bps.sleep(0)

    assert log.run_uid_filter.run_uid is None
    RE(test_plan())
    assert log.run_uid_filter.run_uid is None

    graylog_calls_in_plan = [
        c.args[0]
        for c in mock_GELFTCPHandler_emit.mock_calls
        if c.args[0].msg == "test_hyperion"
    ]

    assert len(graylog_calls_in_plan) == 2

    dc_group_id_correct = [
        record.run_uid == test_run_uid for record in graylog_calls_in_plan
    ]
    assert all(dc_group_id_correct)


@pytest.mark.skip_log_setup
def test_messages_logged_from_dodal_and_hyperion_get_sent_to_graylog_and_file(
    clear_and_mock_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_and_mock_loggers
    log.do_default_logging_setup(dev_mode=True)
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
    clear_and_mock_loggers,
):
    mock_filehandler_emit, mock_GELFTCPHandler_emit = clear_and_mock_loggers
    log.do_default_logging_setup(dev_mode=True)

    hyperion_logger = log.LOGGER
    ispyb_logger = log.ISPYB_LOGGER
    nexus_logger = log.NEXUS_LOGGER
    for logger in [ispyb_logger, nexus_logger]:
        set_up_all_logging_handlers(
            logger, log._get_logging_dir(), logger.name, True, 10000
        )

    hyperion_logger.info("test_hyperion")
    ispyb_logger.info("test_ispyb")
    nexus_logger.info("test_nexus")

    total_filehandler_calls = mock_filehandler_emit.mock_calls
    total_graylog_calls = mock_GELFTCPHandler_emit.mock_calls

    assert len(total_filehandler_calls) == len(total_graylog_calls)

    hyperion_filehandler = next(
        filter(lambda h: isinstance(h, TimedRotatingFileHandler), dodal_logger.handlers)  # type: ignore
    )
    ispyb_filehandler = next(
        filter(lambda h: isinstance(h, TimedRotatingFileHandler), ispyb_logger.handlers)  # type: ignore
    )
    nexus_filehandler = next(
        filter(lambda h: isinstance(h, TimedRotatingFileHandler), nexus_logger.handlers)  # type: ignore
    )
    assert nexus_filehandler.baseFilename != hyperion_filehandler.baseFilename  # type: ignore
    assert ispyb_filehandler.baseFilename != hyperion_filehandler.baseFilename  # type: ignore
    assert ispyb_filehandler.baseFilename != nexus_filehandler.baseFilename  # type: ignore


@pytest.mark.skip_log_setup
def test_log_writes_debug_file_on_error(clear_and_mock_loggers):
    mock_filehandler_emit, _ = clear_and_mock_loggers
    log.do_default_logging_setup(dev_mode=True)
    log.LOGGER.debug("debug_message_1")
    log.LOGGER.debug("debug_message_2")
    mock_filehandler_emit.assert_not_called()
    log.LOGGER.error("error happens")
    assert len(mock_filehandler_emit.mock_calls) == 4
    messages = [call.args[0].message for call in mock_filehandler_emit.mock_calls]
    assert "debug_message_1" in messages
    assert "debug_message_2" in messages
    assert "error happens" in messages
