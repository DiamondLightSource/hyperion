from unittest.mock import MagicMock, call

from artemis.external_interaction.communicator_callbacks import FGSCallbackCollection
from artemis.parameters import FullParameters
from artemis.utils import Point3D


def test_run_gridscan_zocalo_calls(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
    nexus_writer: MagicMock,
    td,
):

    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.ispyb_handler.start(td.test_start_document)
    callbacks.zocalo_handler.start(td.test_start_document)
    callbacks.ispyb_handler.descriptor(td.test_descriptor_document)
    callbacks.zocalo_handler.descriptor(td.test_descriptor_document)
    callbacks.ispyb_handler.event(td.test_event_document)
    callbacks.zocalo_handler.event(td.test_event_document)
    callbacks.ispyb_handler.stop(td.test_stop_document)
    callbacks.zocalo_handler.stop(td.test_stop_document)

    run_start.assert_has_calls([call(x) for x in dc_ids])
    assert run_start.call_count == len(dc_ids)

    run_end.assert_has_calls([call(x) for x in dc_ids])
    assert run_end.call_count == len(dc_ids)

    wait_for_result.assert_not_called()


def test_zocalo_called_to_wait_on_results_when_communicator_wait_for_results_called(
    wait_for_result: MagicMock,
):
    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.ispyb_handler.ispyb_ids = (0, 0, 100)
    expected_centre_grid_coords = Point3D(1, 2, 3)
    wait_for_result.return_value = expected_centre_grid_coords

    callbacks.zocalo_handler.wait_for_results()
    wait_for_result.assert_called_once_with(100)
    expected_centre_motor_coords = (
        params.grid_scan_params.grid_position_to_motor_position(
            expected_centre_grid_coords
        )
    )
    assert (
        callbacks.zocalo_handler.xray_centre_motor_position
        == expected_centre_motor_coords
    )
