from unittest.mock import MagicMock, call, patch

import artemis.external_interaction.tests.testdata as td
from artemis.external_interaction.communicator_callbacks import ISPyBHandlerCallback
from artemis.parameters import FullParameters


@patch(
    "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_fgs_failing_results_in_bad_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
    nexus_writer: MagicMock,
):
    dc_ids = [1, 2]
    dcg_id = 4
    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    ispyb_handler = ISPyBHandlerCallback(params)
    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)
    ispyb_handler.stop(td.test_failed_stop_document)
    mock_ispyb_update_time_and_status.assert_has_calls(
        [
            call(td.DUMMY_TIME_STRING, td.BAD_ISPYB_RUN_STATUS, id, dcg_id)
            for id in dc_ids
        ]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)


@patch(
    "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_fgs_raising_no_exception_results_in_good_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
    nexus_writer: MagicMock,
):
    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    ispyb_handler = ISPyBHandlerCallback(params)
    ispyb_handler.start(td.test_start_document)
    ispyb_handler.descriptor(td.test_descriptor_document)
    ispyb_handler.event(td.test_event_document)
    ispyb_handler.stop(td.test_stop_document)

    mock_ispyb_update_time_and_status.assert_has_calls(
        [
            call(td.DUMMY_TIME_STRING, td.GOOD_ISPYB_RUN_STATUS, id, dcg_id)
            for id in dc_ids
        ]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)
