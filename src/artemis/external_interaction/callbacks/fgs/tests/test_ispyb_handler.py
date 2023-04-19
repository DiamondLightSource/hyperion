import logging
from unittest.mock import MagicMock, call

import pytest

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.tests.conftest import TestData
from artemis.log import LOGGER, set_up_logging_handlers
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)
from artemis.parameters.external_parameters import from_file as default_raw_params

DC_IDS = [1, 2]
DCG_ID = 4
td = TestData()


@pytest.fixture
def dummy_params():
    return FGSInternalParameters(default_raw_params())


def test_fgs_failing_results_in_bad_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    dummy_params,
):
    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    ispyb_handler = FGSISPyBHandlerCallback(dummy_params)
    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)
    ispyb_handler.stop(td.test_run_gridscan_failed_stop_document)
    mock_ispyb_update_time_and_status.assert_has_calls(
        [
            call(
                td.DUMMY_TIME_STRING,
                td.BAD_ISPYB_RUN_STATUS,
                "could not connect to devices",
                id,
                DCG_ID,
            )
            for id in DC_IDS
        ]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(DC_IDS)


def test_fgs_raising_no_exception_results_in_good_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    dummy_params,
):
    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    ispyb_handler = FGSISPyBHandlerCallback(dummy_params)
    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)
    ispyb_handler.stop(td.test_run_gridscan_stop_document)

    mock_ispyb_update_time_and_status.assert_has_calls(
        [
            call(td.DUMMY_TIME_STRING, td.GOOD_ISPYB_RUN_STATUS, "", id, DCG_ID)
            for id in DC_IDS
        ]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(DC_IDS)


@pytest.fixture
def mock_emit():
    set_up_logging_handlers(dev_mode=True)
    test_handler = logging.Handler()
    test_handler.emit = MagicMock()  # type: ignore
    LOGGER.addHandler(test_handler)

    yield test_handler.emit

    LOGGER.removeHandler(test_handler)


def test_given_ispyb_callback_started_writing_to_ispyb_when_messages_logged_then_they_contain_dcgid(
    mock_emit, mock_ispyb_store_grid_scan: MagicMock, dummy_params
):
    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]

    ispyb_handler = FGSISPyBHandlerCallback(dummy_params)

    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)

    LOGGER.info("test")

    latest_record = mock_emit.call_args.args[0]
    assert latest_record.dc_group_id == DCG_ID


def test_given_ispyb_callback_finished_writing_to_ispyb_when_messages_logged_then_they_do_not_contain_dcgid(
    mock_emit,
    mock_ispyb_store_grid_scan: MagicMock,
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    dummy_params,
):
    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    ispyb_handler = FGSISPyBHandlerCallback(dummy_params)

    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)
    ispyb_handler.stop(td.test_run_gridscan_stop_document)

    LOGGER.info("test")

    latest_record = mock_emit.call_args.args[0]
    assert not hasattr(latest_record, "dc_group_id")
