from unittest.mock import MagicMock, patch

import pytest
from graypy import GELFTCPHandler

from hyperion.external_interaction.callbacks.__main__ import setup_logging
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.log import ISPYB_LOGGER

from .conftest import TestData

DC_IDS = (1, 2)
DCG_ID = 4
td = TestData()


def mock_store_in_ispyb(config, *args, **kwargs) -> Store3DGridscanInIspyb:
    mock = Store3DGridscanInIspyb("")
    mock._store_grid_scan = MagicMock(
        return_value=IspybIds(
            data_collection_ids=DC_IDS,
            data_collection_group_id=DCG_ID,
            grid_ids=None,
        )
    )
    mock.end_deposition = MagicMock(return_value=None)
    mock.begin_deposition = MagicMock(
        return_value=IspybIds(
            data_collection_group_id=DCG_ID, data_collection_ids=DC_IDS
        )
    )
    mock.append_to_comment = MagicMock()
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
            td.test_event_document_during_data_collection  # pyright: ignore
        )
        ispyb_handler.activity_gated_stop(td.test_run_gridscan_failed_stop_document)

        ispyb_handler.ispyb.end_deposition.assert_called_once_with(
            "fail", "could not connect to devices", ispyb_handler.params
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

        ispyb_handler.ispyb.end_deposition.assert_called_once_with(
            "success", "", ispyb_handler.params
        )

    @pytest.mark.skip_log_setup
    def test_given_ispyb_callback_started_writing_to_ispyb_when_messages_logged_then_they_contain_dcgid(
        self,
    ):
        setup_logging(True)
        gelf_handler: MagicMock = next(
            filter(lambda h: isinstance(h, GELFTCPHandler), ISPYB_LOGGER.handlers)  # type: ignore
        )
        gelf_handler.emit = MagicMock()

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

        ISPYB_LOGGER.info("test")
        latest_record = gelf_handler.emit.call_args.args[-1]
        assert latest_record.dc_group_id == DCG_ID

    @pytest.mark.skip_log_setup
    def test_given_ispyb_callback_finished_writing_to_ispyb_when_messages_logged_then_they_do_not_contain_dcgid(
        self,
    ):
        setup_logging(True)
        gelf_handler: MagicMock = next(
            filter(lambda h: isinstance(h, GELFTCPHandler), ISPYB_LOGGER.handlers)  # type: ignore
        )
        gelf_handler.emit = MagicMock()

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

        ISPYB_LOGGER.info("test")
        latest_record = gelf_handler.emit.call_args.args[-1]
        assert not hasattr(latest_record, "dc_group_id")

    @patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.time",
        side_effect=[2, 100],
    )
    def test_given_fgs_plan_finished_when_zocalo_results_event_then_expected_comment_deposited(
        self, mock_time
    ):
        ispyb_handler = GridscanISPyBCallback()

        ispyb_handler.activity_gated_start(td.test_start_document)  # type:ignore

        ispyb_handler.activity_gated_start(td.test_do_fgs_start_document)  # type:ignore
        ispyb_handler.activity_gated_stop(td.test_do_fgs_gridscan_stop_document)

        ispyb_handler.activity_gated_descriptor(
            td.test_descriptor_document_zocalo_reading
        )
        ispyb_handler.activity_gated_event(td.test_zocalo_reading_event)

        assert (
            ispyb_handler.ispyb.append_to_comment.call_args.args[1]  # type:ignore
            == "Zocalo processing took 98.00 s. Zocalo found no crystals in this gridscan."
        )
