from unittest.mock import MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine

from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.fast_grid_scan_plan import run_gridscan_and_move
from artemis.fgs_communicator import FGSCommunicator
from artemis.parameters import (
    ISPYB_PLAN_NAME,
    SIM_BEAMLINE,
    SIM_ZOCALO_ENV,
    DetectorParams,
    FullParameters,
)
from artemis.utils import Point3D

DUMMY_TIME_STRING = "1970-01-01 00:00:00"
GOOD_ISPYB_RUN_STATUS = "DataCollection Successful"
BAD_ISPYB_RUN_STATUS = "DataCollection Unsuccessful"

test_start_document = {
    "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604299.6149616,
    "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
    "scan_id": 1,
    "plan_type": "generator",
    "plan_name": "run_gridscan_and_move",
}
test_descriptor_document = {
    "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "name": ISPYB_PLAN_NAME,
}
test_event_document = {
    "descriptor": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
    "time": 1666604299.828203,
    "data": {
        "fgs_slit_gaps_xgap": 0.1234,
        "fgs_slit_gaps_ygap": 0.2345,
        "fgs_synchrotron_machine_status_synchrotron_mode": "test",
        "fgs_undulator_gap": 1.234,
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
test_failed_stop_document = {
    "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604300.0310638,
    "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
    "exit_status": "fail",
    "reason": "",
    "num_events": {"fake_ispyb_params": 1, "primary": 1},
}


def test_fgs_communicator_init():
    communicator = FGSCommunicator(FullParameters())
    assert communicator.params == FullParameters()


@patch("artemis.fgs_communicator.NexusWriter")
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
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
    nexus_writer: MagicMock,
):

    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    communicator = FGSCommunicator(params)
    communicator.start(test_start_document)
    communicator.descriptor(test_descriptor_document)
    communicator.event(test_event_document)
    communicator.stop(test_stop_document)

    run_start.assert_has_calls([call(x, SIM_ZOCALO_ENV) for x in dc_ids])
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls([call(x, SIM_ZOCALO_ENV) for x in dc_ids])
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_not_called()


@patch("artemis.fgs_communicator.wait_for_result")
def test_zocalo_called_to_wait_on_results_when_communicator_wait_for_results_called(
    wait_for_result: MagicMock,
):
    params = FullParameters()
    communicator = FGSCommunicator(params)
    communicator.ispyb_ids = (0, 0, 100)
    expected_centre_grid_coords = Point3D(1, 2, 3)
    wait_for_result.return_value = expected_centre_grid_coords

    communicator.wait_for_results()
    wait_for_result.assert_called_once_with(100, SIM_ZOCALO_ENV)
    expected_centre_motor_coords = (
        params.grid_scan_params.grid_position_to_motor_position(
            expected_centre_grid_coords
        )
    )
    assert communicator.xray_centre_motor_position == expected_centre_motor_coords


@patch("artemis.fgs_communicator.NexusWriter")
@patch("artemis.fgs_communicator.run_start")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fgs_communicator.wait_for_result")
@patch("artemis.fgs_communicator.StoreInIspyb3D.store_grid_scan")
@patch("artemis.fgs_communicator.StoreInIspyb3D.get_current_time_string")
@patch(
    "artemis.fgs_communicator.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
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
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    communicator = FGSCommunicator(params)
    communicator.start(test_start_document)
    communicator.descriptor(test_descriptor_document)
    communicator.event(test_event_document)
    communicator.stop(test_failed_stop_document)
    mock_ispyb_update_time_and_status.assert_has_calls(
        [call(DUMMY_TIME_STRING, BAD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)


@patch("artemis.fgs_communicator.NexusWriter")
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
    nexus_writer: MagicMock,
):
    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    communicator = FGSCommunicator(params)
    communicator.start(test_start_document)
    communicator.descriptor(test_descriptor_document)
    communicator.event(test_event_document)
    communicator.stop(test_stop_document)

    mock_ispyb_update_time_and_status.assert_has_calls(
        [call(DUMMY_TIME_STRING, GOOD_ISPYB_RUN_STATUS, id, dcg_id) for id in dc_ids]
    )
    assert mock_ispyb_update_time_and_status.call_count == len(dc_ids)


@patch("artemis.fgs_communicator.create_parameters_for_first_file")
@patch("artemis.fgs_communicator.create_parameters_for_second_file")
@patch("artemis.fgs_communicator.NexusWriter")
def test_writers_setup_on_init(
    nexus_writer: MagicMock,
    param_for_second: MagicMock,
    param_for_first: MagicMock,
):

    params = FullParameters()
    communicator = FGSCommunicator(params)
    # flake8 gives an error if we don't do something with communicator
    communicator.__init__(params)

    nexus_writer.assert_has_calls(
        [
            call(param_for_first()),
            call(param_for_second()),
        ],
        any_order=True,
    )


@patch("artemis.fgs_communicator.create_parameters_for_first_file")
@patch("artemis.fgs_communicator.create_parameters_for_second_file")
@patch("artemis.fgs_communicator.NexusWriter")
def test_writers_dont_create_on_init(
    nexus_writer: MagicMock,
    param_for_second: MagicMock,
    param_for_first: MagicMock,
):

    params = FullParameters()
    communicator = FGSCommunicator(params)

    communicator.nxs_writer_1.create_nexus_file.assert_not_called()
    communicator.nxs_writer_2.create_nexus_file.assert_not_called()


@patch("artemis.fgs_communicator.NexusWriter")
def test_writers_do_create_one_file_each_on_start_doc(
    nexus_writer: MagicMock,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]

    params = FullParameters()
    communicator = FGSCommunicator(params)
    communicator.start(test_start_document)

    assert communicator.nxs_writer_1.create_nexus_file.call_count == 1
    assert communicator.nxs_writer_2.create_nexus_file.call_count == 1


@pytest.fixture()
def eiger():
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
    )
    eiger = EigerDetector(
        detector_params=detector_params, name="eiger", prefix="BL03S-EA-EIGER-01:"
    )

    # Otherwise odin moves too fast to be tested
    eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    eiger.wait_for_stale_parameters = lambda: None
    eiger.odin.check_odin_initialised = lambda: (True, "")

    yield eiger


@pytest.mark.skip(reason="Needs better S03 or some other workaround.")
@pytest.mark.s03
@patch("artemis.fgs_communicator.StoreInIspyb3D.end_deposition")
@patch("artemis.fgs_communicator.StoreInIspyb3D.begin_deposition")
@patch("artemis.fgs_communicator.NexusWriter")
@patch("artemis.fgs_communicator.wait_for_result")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fgs_communicator.run_start")
def test_communicator_in_composite_run(
    run_start: MagicMock,
    run_end: MagicMock,
    wait_for_result: MagicMock,
    nexus_writer: MagicMock,
    ispyb_begin_deposition: MagicMock,
    ispyb_end_deposition: MagicMock,
    eiger: EigerDetector,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]
    RE = RunEngine({})

    params = FullParameters()
    params.beamline = SIM_BEAMLINE
    ispyb_begin_deposition.return_value = ([1, 2], None, 4)
    communicator = FGSCommunicator(params)
    communicator.xray_centre_motor_position = Point3D(1, 2, 3)

    fast_grid_scan_composite = FGSComposite(
        insertion_prefix=params.insertion_prefix,
        name="fgs",
        prefix=params.beamline,
    )
    # this is where it's currently getting stuck:
    # fast_grid_scan_composite.fast_grid_scan.is_invalid = lambda: False
    # but this is not a solution
    fast_grid_scan_composite.wait_for_connection()
    # Would be better to use get_plan instead but eiger doesn't work well in S03
    RE(run_gridscan_and_move(fast_grid_scan_composite, eiger, params, communicator))

    # nexus writing
    communicator.nxs_writer_1.assert_called_once()
    communicator.nxs_writer_2.assert_called_once()
    # ispyb
    ispyb_begin_deposition.assert_called_once()
    ispyb_end_deposition.assert_called_once()
    # zocalo
    run_start.assert_called()
    run_end.assert_called()
    wait_for_result.assert_called_once()
