from unittest.mock import MagicMock, call, patch

import pytest

from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.callbacks.zocalo_callback import ZocaloCallback
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.ispyb_store import IspybIds, StoreInIspyb
from hyperion.parameters.constants import CONST

from .xray_centre.conftest import TestData

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}

td = TestData()


class TestZocaloHandler:
    def _setup_handler(self):
        zocalo_handler = ZocaloCallback()
        assert zocalo_handler.triggering_plan is None
        zocalo_handler.start({CONST.TRIGGER.ZOCALO: "test_plan_name"})  # type: ignore
        assert zocalo_handler.triggering_plan == "test_plan_name"
        assert zocalo_handler.zocalo_interactor is None
        return zocalo_handler

    def test_handler_gets_plan_name_from_start_doc(self):
        self._setup_handler()

    def test_handler_doesnt_trigger_on_wrong_plan(self):
        zocalo_handler = self._setup_handler()
        zocalo_handler.start({CONST.TRIGGER.ZOCALO: "_not_test_plan_name"})  # type: ignore

    def test_handler_raises_on_right_plan_with_wrong_metadata(self):
        zocalo_handler = self._setup_handler()
        assert zocalo_handler.zocalo_interactor is None
        with pytest.raises(AssertionError):
            zocalo_handler.start({"subplan_name": "test_plan_name"})  # type: ignore

    def test_handler_raises_on_right_plan_with_no_ispyb_ids(self):
        zocalo_handler = self._setup_handler()
        assert zocalo_handler.zocalo_interactor is None
        with pytest.raises(ISPyBDepositionNotMade):
            zocalo_handler.start(
                {"subplan_name": "test_plan_name", "zocalo_environment": "test_env"}  # type: ignore
            )

    @patch(
        "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
        autospec=True,
    )
    def test_handler_inits_zocalo_trigger_on_right_plan(self, zocalo_trigger):
        zocalo_handler = self._setup_handler()
        assert zocalo_handler.zocalo_interactor is None
        zocalo_handler.start(
            {
                "subplan_name": "test_plan_name",
                "zocalo_environment": "test_env",
                "ispyb_dcids": (135, 139),
            }  # type: ignore
        )
        assert zocalo_handler.zocalo_interactor is not None

    @patch(
        "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
        autospec=True,
    )
    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter",
    )
    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
    )
    def test_execution_of_do_fgs_triggers_zocalo_calls(
        self, ispyb_store: MagicMock, nexus_writer: MagicMock, zocalo_trigger
    ):
        dc_ids = (1, 2)
        dcg_id = 4

        mock_ids = IspybIds(
            data_collection_ids=dc_ids, grid_ids=None, data_collection_group_id=dcg_id
        )
        ispyb_store.return_value.mock_add_spec(StoreInIspyb)

        callbacks = XrayCentreCallbackCollection()
        ispyb_cb = callbacks.ispyb_handler
        ispyb_cb.active = True
        assert isinstance(zocalo_handler := ispyb_cb.emit_cb, ZocaloCallback)
        zocalo_handler._reset_state()
        zocalo_handler._reset_state = MagicMock()

        ispyb_store.return_value.begin_deposition.return_value = mock_ids
        ispyb_store.return_value.update_deposition.return_value = mock_ids

        ispyb_cb.start(td.test_start_document)  # type: ignore
        ispyb_cb.start(td.test_do_fgs_start_document)  # type: ignore
        ispyb_cb.descriptor(
            td.test_descriptor_document_pre_data_collection
        )  # type: ignore
        ispyb_cb.event(td.test_event_document_pre_data_collection)
        ispyb_cb.descriptor(
            td.test_descriptor_document_during_data_collection  # type: ignore
        )
        ispyb_cb.event(td.test_event_document_during_data_collection)
        assert zocalo_handler.zocalo_interactor is not None

        zocalo_handler.zocalo_interactor.run_start.assert_has_calls(  # type: ignore
            [call(x) for x in dc_ids]
        )
        assert zocalo_handler.zocalo_interactor.run_start.call_count == len(dc_ids)  # type: ignore

        ispyb_cb.stop(td.test_stop_document)

        zocalo_handler.zocalo_interactor.run_end.assert_has_calls(  # type: ignore
            [call(x) for x in dc_ids]
        )
        assert zocalo_handler.zocalo_interactor.run_end.call_count == len(dc_ids)  # type: ignore

        zocalo_handler._reset_state.assert_called()
