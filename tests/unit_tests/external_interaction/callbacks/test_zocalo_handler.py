from unittest.mock import MagicMock, call, patch

import pytest
from dodal.devices.zocalo import ZocaloTrigger

from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.callbacks.zocalo_callback import ZocaloCallback
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.ispyb_store import IspybIds
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

from ...experiment_plans.conftest import modified_store_grid_scan_mock
from .xray_centre.conftest import TestData

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


@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    new=MagicMock(spec=ZocaloTrigger),
)
class TestZocaloHandler:
    def test_handler_gets_plan_name_from_start_doc(self):
        zocalo_handler = ZocaloCallback()
        assert zocalo_handler.triggering_plan is None
        zocalo_handler.start({"trigger_zocalo_on": "test_plan_name"})  # type: ignore
        assert zocalo_handler.triggering_plan == "test_plan_name"
        assert zocalo_handler.zocalo_interactor is None
        return zocalo_handler

    def test_handler_doesnt_trigger_on_wrong_plan(self):
        zocalo_handler = self.test_handler_gets_plan_name_from_start_doc()
        zocalo_handler.start(
            {"trigger_zocalo_on": "_not_test_plan_name"}  # type: ignore
        )

    def test_handler_raises_on_right_plan_with_wrong_metadata(self):
        zocalo_handler = self.test_handler_gets_plan_name_from_start_doc()
        assert zocalo_handler.zocalo_interactor is None
        with pytest.raises(AssertionError):
            zocalo_handler.start({"subplan_name": "test_plan_name"})  # type: ignore

    def test_handler_raises_on_right_plan_with_no_ispyb_ids(self):
        zocalo_handler = self.test_handler_gets_plan_name_from_start_doc()
        assert zocalo_handler.zocalo_interactor is None
        with pytest.raises(ISPyBDepositionNotMade):
            zocalo_handler.start(
                {"subplan_name": "test_plan_name", "zocalo_environment": "test_env"}  # type: ignore
            )

    def test_handler_inits_zocalo_trigger_on_right_plan(self):
        zocalo_handler = self.test_handler_gets_plan_name_from_start_doc()
        assert zocalo_handler.zocalo_interactor is None
        zocalo_handler.start(
            {
                "subplan_name": "test_plan_name",
                "zocalo_environment": "test_env",
                "ispyb_dcids": (135, 139),
            }  # type: ignore
        )
        assert isinstance(zocalo_handler.zocalo_interactor, ZocaloTrigger)
        zocalo_handler.zocalo_interactor

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

        callbacks = XrayCentreCallbackCollection()
        assert isinstance(
            zocalo_handler := callbacks.ispyb_handler.emit_cb, ZocaloCallback
        )
        init_cbs_with_docs_and_mock_zocalo_and_ispyb(callbacks, dc_ids, dcg_id)
        callbacks.ispyb_handler.activity_gated_start(
            td.test_run_gridscan_start_document
        )  # type: ignore
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
        zocalo_handler.start(td.test_do_fgs_start_document)
        callbacks.ispyb_handler.activity_gated_stop(td.test_stop_document)
        zocalo_handler.stop(td.test_stop_document)

        assert zocalo_handler.zocalo_interactor is not None

        zocalo_handler.zocalo_interactor.run_start.assert_has_calls(
            [call(x) for x in dc_ids]
        )
        assert zocalo_handler.zocalo_interactor.run_start.call_count == len(dc_ids)

        zocalo_handler.zocalo_interactor.run_end.assert_has_calls(
            [call(x) for x in dc_ids]
        )
        assert zocalo_handler.zocalo_interactor.run_end.call_count == len(dc_ids)

    def test_GIVEN_ispyb_not_started_WHEN_trigger_zocalo_handler_THEN_raises_exception(
        self,
        dummy_params,
    ):
        callbacks = XrayCentreCallbackCollection()

        with pytest.raises(ISPyBDepositionNotMade):
            assert isinstance(callbacks.ispyb_handler.emit_cb, ZocaloCallback)
            callbacks.ispyb_handler.emit_cb.start(td.test_do_fgs_start_document)
