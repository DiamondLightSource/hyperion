from unittest.mock import MagicMock, call

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.tests.conftest import TestData
from artemis.parameters import FullParameters

DC_IDS = [1, 2]
DCG_ID = 4
td = TestData()


def test_fgs_failing_results_in_bad_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    nexus_writer: MagicMock,
):

    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    ispyb_handler = FGSISPyBHandlerCallback(params)
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
    nexus_writer: MagicMock,
):

    mock_ispyb_store_grid_scan.return_value = [DC_IDS, None, DCG_ID]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    ispyb_handler = FGSISPyBHandlerCallback(params)
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
