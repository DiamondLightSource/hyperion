from unittest.mock import MagicMock, call, patch

from artemis import fgs_communicator
from artemis.parameters import FullParameters

DUMMY_TIME_STRING = "1970-01-01 00:00:00"
GOOD_ISPYB_RUN_STATUS = "DataCollection Successful"
BAD_ISPYB_RUN_STATUS = "DataCollection Unsuccessful"

test_start_document = {
    "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604299.6149616,
    "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
    "scan_id": 1,
    "plan_type": "generator",
    "plan_name": "run_gridscan",
}
test_event_document = {
    "descriptor": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "name": "ispyb_motor_positions",
    "time": 1666604299.828203,
    "data": {
        "slit_gaps_xgap": 0.1234,
        "slit_gaps_ygap": 0.2345,
        "synchrotron_machine_status_synchrotron_mode": "test",
        "undulator_gap": 1.234,
    },
    "timestamps": {"det1": 1666604299.8220396, "det2": 1666604299.8235943},
    "seq_num": 1,
    "uid": "29033ecf-e052-43dd-98af-c7cdd62e8173",
    "filled": {},
}
test_stop_document = {
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604300.0310638,
    "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
    "exit_status": "success",
    "reason": "",
    "num_events": {"fake_ispyb_params": 1, "primary": 1},
}
test_descriptor_document = {
    "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
}


def test_fgs_communicator_reset():
    communicator = fgs_communicator.FGSCommunicator()
    assert communicator.processing_time is None
    assert communicator.active_uid is None
    communicator.params.detector_params.prefix = "file_name"
    assert communicator.params == FullParameters()

    communicator.results = "some position to move to"
    communicator.reset(FullParameters())
    assert communicator.results is None


def test_start_sets_uid():
    communicator = fgs_communicator.FGSCommunicator()
    communicator.start({"uid": "some uid"})
    assert communicator.active_uid == "some uid"


# TODO should no longer except, test in different way
# def test_stop_excepts_on_wrong_uid():
#     communicator = fgs_communicator.FGSCommunicator()
#     communicator.start({"uid": "some uid", "scan_type": "gridscan"})
#     with pytest.raises(Exception):
#         communicator.stop({"run_start": "some other uid", "scan_type": "gridscan"})


def test_stop_doesnt_except_on_correct_uid():
    communicator = fgs_communicator.FGSCommunicator()
    communicator.start({"uid": "some uid", "scan_type": "gridscan"})
    communicator.stop({"run_start": "some uid"})


# TODO MOVE TO TEST COMMUNICATOR
@patch("artemis.fgs_communicator.run_start")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fgs_communicator.wait_for_result")
@patch("artemis.fgs_communicator.StoreInIspyb3D.store_grid_scan")
@patch("artemis.fgs_communicator.StoreInIspyb3D.get_current_time_string")
@patch(
    "artemis.fgs_communicator.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_run_gridscan_zocalo_calls(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result,
    run_end,
    run_start,
):

    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    communicator = fgs_communicator.FGSCommunicator()
    communicator.params = FullParameters()
    communicator.start(test_start_document)
    communicator.descriptor(test_descriptor_document)
    communicator.event(test_event_document)
    communicator.stop(test_stop_document)

    run_start.assert_has_calls(call(x) for x in dc_ids)
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls(call(x) for x in dc_ids)
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_called_once_with(dcg_id)


# @patch("artemis.fast_grid_scan_plan.run_start")
# @patch("artemis.fast_grid_scan_plan.run_end")
# @patch("artemis.fast_grid_scan_plan.wait_for_result")
# @patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.store_grid_scan")
# @patch("artemis.fast_grid_scan_plan.StoreInIspyb3D.get_current_time_string")
# @patch(
#     "artemis.fast_grid_scan_plan.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
# )
# def test_fgs_raising_exception_results_in_bad_run_status_in_ispyb(
#     mock_ispyb_update_time_and_status: MagicMock,
#     mock_ispyb_get_time: MagicMock,
#     mock_ispyb_store_grid_scan: MagicMock,
#     wait_for_result: MagicMock,
#     run_end: MagicMock,
#     run_start: MagicMock,
#     dummy_3d_gridscan_args,
# ):
#     dc_ids = [1, 2]
#     dcg_id = 4
#
#     mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
#     mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
#     mock_ispyb_update_time_and_status.return_value = None
#
#     with pytest.raises(Exception) as excinfo:
#         with patch(
#             "artemis.fgs_communicator.NexusWriter",
#             side_effect=Exception("mocked error"),
#         ):
#             list(run_gridscan(*dummy_3d_gridscan_args))
#
#     expected_error_message = "mocked error"
#     assert str(excinfo.value) == expected_error_message
#
#     mock_ispyb_update_time_and_status.assert_has_calls(
#         [call(DUMMY_TIME_STRING, BAD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
#     )
#     assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)


@patch("artemis.fgs_communicator.run_start")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fgs_communicator.wait_for_result")
@patch("artemis.fgs_communicator.StoreInIspyb3D.store_grid_scan")
@patch("artemis.fgs_communicator.StoreInIspyb3D.get_current_time_string")
@patch(
    "artemis.fgs_communicator.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
)
def test_fgs_raising_no_exception_results_in_good_run_status_in_ispyb(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
):
    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    communicator = fgs_communicator.FGSCommunicator()
    communicator.params = FullParameters()
    communicator.start(test_start_document)
    communicator.descriptor(test_descriptor_document)
    communicator.event(test_event_document)
    communicator.stop(test_stop_document)

    mock_ispyb_update_time_and_status.assert_has_calls(
        [call(DUMMY_TIME_STRING, GOOD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)
