from unittest.mock import patch

import pytest

from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.parameters.constants import (
    GRIDSCAN_AND_MOVE,
    GRIDSCAN_MAIN_PLAN,
    GRIDSCAN_OUTER_PLAN,
    ISPYB_HARDWARE_READ_PLAN,
    ISPYB_TRANSMISSION_FLUX_READ_PLAN,
)
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


@pytest.fixture
def nexus_writer():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter"
    ) as nw:
        yield nw


@pytest.fixture
def mock_ispyb_get_time():
    with patch(
        "hyperion.external_interaction.ispyb.ispyb_utils.get_current_time_string"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_store_grid_scan():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.store_grid_scan"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_update_time_and_status():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.update_scan_with_end_time_and_status"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_begin_deposition():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.begin_deposition"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_end_deposition():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.end_deposition"
    ) as p:
        yield p


@pytest.fixture
def ispyb_handler():
    return GridscanISPyBCallback()


def dummy_params():
    dummy_params = GridscanInternalParameters(**default_raw_params())
    return dummy_params


class TestData:
    DUMMY_TIME_STRING: str = "1970-01-01 00:00:00"
    GOOD_ISPYB_RUN_STATUS: str = "DataCollection Successful"
    BAD_ISPYB_RUN_STATUS: str = "DataCollection Unsuccessful"
    test_start_document: dict = {
        "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604299.6149616,
        "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
        "scan_id": 1,
        "plan_type": "generator",
        "plan_name": GRIDSCAN_OUTER_PLAN,
        "subplan_name": GRIDSCAN_OUTER_PLAN,
        "hyperion_internal_parameters": dummy_params().json(),
    }
    test_run_gridscan_start_document: dict = {
        "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604299.6149616,
        "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
        "scan_id": 1,
        "plan_type": "generator",
        "plan_name": GRIDSCAN_AND_MOVE,
        "subplan_name": GRIDSCAN_MAIN_PLAN,
    }
    test_do_fgs_start_document: dict = {
        "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604299.6149616,
        "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
        "scan_id": 1,
        "plan_type": "generator",
        "plan_name": GRIDSCAN_AND_MOVE,
        "subplan_name": "do_fgs",
    }
    test_descriptor_document_pre_data_collection: dict = {
        "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "name": ISPYB_HARDWARE_READ_PLAN,
    }
    test_descriptor_document_during_data_collection: dict = {
        "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "name": ISPYB_TRANSMISSION_FLUX_READ_PLAN,
    }
    test_event_document_pre_data_collection: dict = {
        "descriptor": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
        "time": 1666604299.828203,
        "data": {
            "s4_slit_gaps_xgap": 0.1234,
            "s4_slit_gaps_ygap": 0.2345,
            "synchrotron_machine_status_synchrotron_mode": "test",
            "undulator_current_gap": 1.234,
            "robot-barcode": "BARCODE",
        },
        "timestamps": {"det1": 1666604299.8220396, "det2": 1666604299.8235943},
        "seq_num": 1,
        "uid": "29033ecf-e052-43dd-98af-c7cdd62e8173",
        "filled": {},
    }
    test_event_document_during_data_collection: dict = {
        "descriptor": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
        "time": 2666604299.928203,
        "data": {
            "attenuator_actual_transmission": 1,
            "flux_flux_reading": 10,
            "dcm_energy_in_kev": 11.105,
        },
        "timestamps": {"det1": 1666604299.8220396, "det2": 1666604299.8235943},
        "seq_num": 1,
        "uid": "29033ecf-e052-43dd-98af-c7cdd62e8174",
        "filled": {},
    }
    test_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "success",
        "reason": "",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
    }
    test_run_gridscan_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "success",
        "reason": "",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
        "subplan_name": GRIDSCAN_MAIN_PLAN,
    }
    test_do_fgs_gridscan_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "success",
        "reason": "",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
        "subplan_name": "do_fgs",
    }
    test_failed_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "fail",
        "reason": "could not connect to devices",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
    }
    test_run_gridscan_failed_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "fail",
        "reason": "could not connect to devices",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
        "subplan_name": GRIDSCAN_MAIN_PLAN,
    }
