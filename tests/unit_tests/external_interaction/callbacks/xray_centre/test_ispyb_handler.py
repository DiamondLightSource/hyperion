from unittest.mock import MagicMock, call, patch

import pytest
from dodal.log import LOGGER as dodal_logger

from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.log import (
    ISPYB_LOGGER,
    set_up_logging_handlers,
)

from .conftest import TestData

DC_IDS = (1, 2)
DCG_ID = 4
td = TestData()


@pytest.fixture
def mock_emits():
    with patch("hyperion.log.setup_dodal_logging"):
        handlers = set_up_logging_handlers(dev_mode=True)
    for h in handlers:
        h.emit = MagicMock()
    emits = [h.emit for h in handlers]

    yield emits


def mock_store_in_ispyb(config, params, *args, **kwargs) -> Store3DGridscanInIspyb:
    mock = Store3DGridscanInIspyb("", params)
    mock._store_grid_scan = MagicMock(return_value=[DC_IDS, None, DCG_ID])
    mock._update_scan_with_end_time_and_status = MagicMock(return_value=None)
    mock.begin_deposition = MagicMock(
        return_value=IspybIds(
            data_collection_group_id=DCG_ID, data_collection_ids=DC_IDS
        )
    )
    return mock


@patch(
    "hyperion.external_interaction.ispyb.ispyb_store.get_current_time_string",
    MagicMock(return_value=td.DUMMY_TIME_STRING),
)
@patch(
    "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb",
    mock_store_in_ispyb,
)
class TestXrayCentreIspybHandler:
    def test_fgs_failing_results_in_bad_run_status_in_ispyb(
        self,
    ):
        ispyb_handler = GridscanISPyBCallback()
        ispyb_handler.activity_gated_start(td.test_start_document)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )
        ispyb_handler.activity_gated_event(td.test_event_document_pre_data_collection)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection
        )
        ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )
        ispyb_handler.activity_gated_stop(td.test_run_gridscan_failed_stop_document)

        ispyb_handler.ispyb._update_scan_with_end_time_and_status.assert_has_calls(
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
        assert (
            ispyb_handler.ispyb._update_scan_with_end_time_and_status.call_count
            == len(DC_IDS)
        )

    def test_fgs_raising_no_exception_results_in_good_run_status_in_ispyb(
        self,
    ):
        ispyb_handler = GridscanISPyBCallback()
        ispyb_handler.activity_gated_start(td.test_start_document)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )
        ispyb_handler.activity_gated_event(td.test_event_document_pre_data_collection)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection
        )
        ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )
        ispyb_handler.activity_gated_stop(td.test_do_fgs_gridscan_stop_document)

        ispyb_handler.ispyb._update_scan_with_end_time_and_status.assert_has_calls(
            [
                call(
                    td.DUMMY_TIME_STRING,
                    td.GOOD_ISPYB_RUN_STATUS,
                    "",
                    id,
                    DCG_ID,
                )
                for id in DC_IDS
            ]
        )
        assert (
            ispyb_handler.ispyb._update_scan_with_end_time_and_status.call_count
            == len(DC_IDS)
        )

    def test_given_ispyb_callback_started_writing_to_ispyb_when_messages_logged_then_they_contain_dcgid(
        self, mock_emits
    ):
        ispyb_handler = GridscanISPyBCallback()
        ispyb_handler.activity_gated_start(td.test_start_document)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )
        ispyb_handler.activity_gated_event(td.test_event_document_pre_data_collection)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection
        )
        ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )

        for logger in [ISPYB_LOGGER, dodal_logger]:
            logger.info("test")
            for emit in mock_emits:
                latest_record = emit.call_args.args[-1]
                assert latest_record.dc_group_id == DCG_ID

    def test_given_ispyb_callback_finished_writing_to_ispyb_when_messages_logged_then_they_do_not_contain_dcgid(
        self,
        mock_emits,
    ):
        ispyb_handler = GridscanISPyBCallback()
        ispyb_handler.activity_gated_start(td.test_start_document)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_pre_data_collection
        )
        ispyb_handler.activity_gated_event(td.test_event_document_pre_data_collection)
        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_during_data_collection
        )
        ispyb_handler.activity_gated_event(
            td.test_event_document_during_data_collection
        )
        ispyb_handler.activity_gated_stop(td.test_run_gridscan_failed_stop_document)

        for logger in [ISPYB_LOGGER, dodal_logger]:
            logger.info("test")
            for emit in mock_emits:
                latest_record = emit.call_args.args[-1]
                assert not hasattr(latest_record, "dc_group_id")
