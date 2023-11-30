from unittest.mock import MagicMock, call, patch

import pytest

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

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
        autospec=True,
    )
    def test_GIVEN_no_results_from_zocalo_WHEN_communicator_wait_for_results_called_THEN_fallback_centre_used(
        self,
        store_3d_grid_scan,
        dummy_params,
    ):
        pass
        # TODO reimplement

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
