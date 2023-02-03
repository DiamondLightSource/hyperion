from unittest.mock import MagicMock, call

import pytest

from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.tests.conftest import TestData
from artemis.external_interaction.zocalo.zocalo_interaction import NoDiffractionFound
from artemis.parameters import FullParameters
from artemis.utils import Point3D

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}

td = TestData()


def mock_zocalo_functions(callbacks: FGSCallbackCollection):
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = MagicMock()


def test_execution_of_run_gridscan_triggers_zocalo_calls(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    nexus_writer: MagicMock,
):

    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    mock_zocalo_functions(callbacks)

    callbacks.ispyb_handler.start(td.test_start_document)
    callbacks.zocalo_handler.start(td.test_start_document)
    callbacks.ispyb_handler.descriptor(td.test_descriptor_document)
    callbacks.zocalo_handler.descriptor(td.test_descriptor_document)
    callbacks.ispyb_handler.event(td.test_event_document)
    callbacks.zocalo_handler.event(td.test_event_document)
    callbacks.ispyb_handler.stop(td.test_stop_document)
    callbacks.zocalo_handler.stop(td.test_stop_document)

    callbacks.zocalo_handler.zocalo_interactor.run_start.assert_has_calls(
        [call(x) for x in dc_ids]
    )
    assert callbacks.zocalo_handler.zocalo_interactor.run_start.call_count == len(
        dc_ids
    )

    callbacks.zocalo_handler.zocalo_interactor.run_end.assert_has_calls(
        [call(x) for x in dc_ids]
    )
    assert callbacks.zocalo_handler.zocalo_interactor.run_end.call_count == len(dc_ids)

    callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_not_called()


def test_zocalo_handler_raises_assertionerror_when_ispyb_has_no_descriptor(
    nexus_writer: MagicMock,
):

    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    mock_zocalo_functions(callbacks)
    callbacks.zocalo_handler.start(td.test_start_document)
    callbacks.zocalo_handler.descriptor(td.test_descriptor_document)
    with pytest.raises(AssertionError):
        callbacks.zocalo_handler.event(td.test_event_document)


def test_zocalo_called_to_wait_on_results_when_communicator_wait_for_results_called():
    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    mock_zocalo_functions(callbacks)
    callbacks.ispyb_handler.ispyb_ids = (0, 0, 100)
    expected_centre_grid_coords = Point3D(1, 2, 3)
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        expected_centre_grid_coords
    )

    found_centre = callbacks.zocalo_handler.wait_for_results(Point3D(0, 0, 0))
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_called_once_with(
        100
    )
    expected_centre_motor_coords = (
        params.grid_scan_params.grid_position_to_motor_position(
            Point3D(
                expected_centre_grid_coords.x - 0.5,
                expected_centre_grid_coords.y - 0.5,
                expected_centre_grid_coords.z - 0.5,
            )
        )
    )
    assert found_centre == expected_centre_motor_coords


def test_GIVEN_no_results_from_zocalo_WHEN_communicator_wait_for_results_called_THEN_fallback_centre_used():
    params = FullParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    mock_zocalo_functions(callbacks)
    callbacks.ispyb_handler.ispyb_ids = (0, 0, 100)
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result.side_effect = (
        NoDiffractionFound()
    )

    fallback_position = Point3D(1, 2, 3)

    found_centre = callbacks.zocalo_handler.wait_for_results(fallback_position)
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_called_once_with(
        100
    )
    assert found_centre == fallback_position
