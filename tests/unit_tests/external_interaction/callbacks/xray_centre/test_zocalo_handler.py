from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
from dodal.devices.zocalo.zocalo_interaction import NoDiffractionFound

from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.store_in_ispyb import IspybIds
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ....experiment_plans.conftest import modified_store_grid_scan_mock
from ....external_interaction.callbacks.xray_centre.conftest import TestData

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}

td = TestData()


@pytest.fixture
def dummy_params():
    return GridscanInternalParameters(**default_raw_params())


def init_cbs_with_docs_and_mock_zocalo_and_ispyb(
    callbacks: XrayCentreCallbackCollection, dcids=(0, 0), dcgid=4
):
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        lambda _, __: modified_store_grid_scan_mock(dcids=dcids, dcgid=dcgid),
    ):
        callbacks.ispyb_handler.activity_gated_start(td.test_start_document)
        callbacks.zocalo_handler.activity_gated_start(td.test_start_document)
    callbacks.zocalo_handler.zocalo_interactor.wait_for_result = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = MagicMock()


class TestXrayCentreZocaloHandler:
    def test_execution_of_run_gridscan_triggers_zocalo_calls(
        self,
        mock_ispyb_update_time_and_status: MagicMock,
        mock_ispyb_get_time: MagicMock,
        mock_ispyb_store_grid_scan: MagicMock,
        nexus_writer: MagicMock,
        dummy_params,
    ):
        dc_ids = (1, 2)
        dcg_id = 4

        mock_ispyb_store_grid_scan.return_value = IspybIds(
            data_collection_ids=dc_ids, grid_ids=None, data_collection_group_id=dcg_id
        )
        mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
        mock_ispyb_update_time_and_status.return_value = None

        callbacks = XrayCentreCallbackCollection.setup()
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks, dc_ids, dcg_id)
        callbacks.ispyb_handler.activity_gated_start(td.test_run_gridscan_start_document)  # type: ignore
        callbacks.zocalo_handler.activity_gated_start(
            td.test_run_gridscan_start_document
        )
        callbacks.ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )  # type: ignore
        callbacks.ispyb_handler.activity_gated_event(
            td.test_event_document_pre_data_collection
        )
        callbacks.ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection  # type: ignore
        )
        callbacks.ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )
        callbacks.zocalo_handler.activity_gated_start(td.test_do_fgs_start_document)
        callbacks.ispyb_handler.activity_gated_stop(td.test_stop_document)
        callbacks.zocalo_handler.activity_gated_stop(td.test_stop_document)

        callbacks.zocalo_handler.zocalo_interactor.run_start.assert_has_calls(
            [call(x) for x in dc_ids]
        )
        assert callbacks.zocalo_handler.zocalo_interactor.run_start.call_count == len(
            dc_ids
        )

        callbacks.zocalo_handler.zocalo_interactor.run_end.assert_has_calls(
            [call(x) for x in dc_ids]
        )
        assert callbacks.zocalo_handler.zocalo_interactor.run_end.call_count == len(
            dc_ids
        )

        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_not_called()

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        autospec=True,
    )
    def test_zocalo_called_to_wait_on_results_when_communicator_wait_for_results_called(
        self,
        store_3d_grid_scan,
        dummy_params: GridscanInternalParameters,
    ):
        callbacks = XrayCentreCallbackCollection.setup()
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks)
        callbacks.ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )
        callbacks.ispyb_handler.activity_gated_event(
            td.test_event_document_pre_data_collection
        )

        callbacks.ispyb_handler.activity_gated_start(td.test_run_gridscan_start_document)  # type: ignore
        callbacks.ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection  # type: ignore
        )
        callbacks.ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )

        callbacks.ispyb_handler.ispyb_ids = IspybIds(
            data_collection_ids=(0, 0), data_collection_group_id=100, grid_ids=(0, 0)
        )
        expected_centre_grid_coords = np.array([1, 2, 3])
        single_crystal_result = [
            {
                "max_voxel": [1, 2, 3],
                "centre_of_mass": expected_centre_grid_coords,
                "bounding_box": [[1, 1, 1], [2, 2, 2]],
                "total_count": 192512.0,
            }
        ]
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
            single_crystal_result
        )
        results = callbacks.zocalo_handler.wait_for_results(np.array([0, 0, 0]))

        found_centre = results[0]
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_called_once_with(
            100
        )
        expected_centre_motor_coords = (
            dummy_params.experiment_params.grid_position_to_motor_position(
                expected_centre_grid_coords - 0.5
            )
        )
        np.testing.assert_array_equal(found_centre, expected_centre_motor_coords)

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        autospec=True,
    )
    def test_GIVEN_no_results_from_zocalo_WHEN_communicator_wait_for_results_called_THEN_fallback_centre_used(
        self,
        store_3d_grid_scan,
        dummy_params,
    ):
        callbacks = XrayCentreCallbackCollection.setup()
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks)
        callbacks.ispyb_handler.ispyb_ids = IspybIds(
            data_collection_ids=(0, 0), data_collection_group_id=100, grid_ids=(0, 0)
        )
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.side_effect = (
            NoDiffractionFound()
        )

        fallback_position = np.array([1, 2, 3])

        found_centre = callbacks.zocalo_handler.wait_for_results(fallback_position)[0]
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_called_once_with(
            100
        )
        np.testing.assert_array_equal(found_centre, fallback_position)

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        autospec=True,
    )
    def test_GIVEN_ispyb_not_started_WHEN_trigger_zocalo_handler_THEN_raises_exception(
        self,
        store_3d_grid_scan,
        dummy_params,
    ):
        callbacks = XrayCentreCallbackCollection.setup()
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks)

        with pytest.raises(ISPyBDepositionNotMade):
            callbacks.zocalo_handler.activity_gated_start(td.test_do_fgs_start_document)

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        autospec=True,
    )
    def test_multiple_results_from_zocalo_sorted_by_total_count_returns_centre_and_bbox_from_first(
        self,
        store_3d_grid_scan,
        dummy_params: GridscanInternalParameters,
    ):
        callbacks = XrayCentreCallbackCollection.setup()
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks)
        callbacks.ispyb_handler.ispyb_ids = IspybIds(
            data_collection_ids=(0, 0), data_collection_group_id=100, grid_ids=(0, 0)
        )
        expected_centre_grid_coords = np.array([4, 6, 2])
        multi_crystal_result = [
            {
                "max_voxel": [1, 2, 3],
                "centre_of_mass": np.array([3, 11, 11]),
                "bounding_box": [[1, 1, 1], [3, 3, 3]],
                "n_voxels": 2,
                "total_count": 192512.0,
            },
            {
                "max_voxel": [1, 2, 3],
                "centre_of_mass": expected_centre_grid_coords,
                "bounding_box": [[2, 2, 2], [8, 8, 7]],
                "n_voxels": 65,
                "total_count": 6671044.0,
            },
        ]
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
            multi_crystal_result
        )
        found_centre, found_bbox = callbacks.zocalo_handler.wait_for_results(
            np.array([0, 0, 0])
        )
        callbacks.zocalo_handler.zocalo_interactor.wait_for_result.assert_called_once_with(
            100
        )
        expected_centre_motor_coords = (
            dummy_params.experiment_params.grid_position_to_motor_position(
                np.array(
                    [
                        expected_centre_grid_coords[0] - 0.5,
                        expected_centre_grid_coords[1] - 0.5,
                        expected_centre_grid_coords[2] - 0.5,
                    ]
                )
            )
        )
        np.testing.assert_array_equal(found_centre, expected_centre_motor_coords)
        assert isinstance(found_bbox, np.ndarray)
        expected_bbox_size = np.array([8, 8, 7]) - np.array([2, 2, 2])
        np.testing.assert_array_equal(found_bbox, expected_bbox_size)  # type: ignore
