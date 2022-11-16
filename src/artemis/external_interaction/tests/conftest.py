from unittest.mock import patch

import pytest

from artemis.parameters import ISPYB_PLAN_NAME


@pytest.fixture
def nexus_writer():
    with patch("artemis.external_interaction.communicator_callbacks.NexusWriter") as nw:
        yield nw


@pytest.fixture
def run_start():
    with patch("artemis.external_interaction.communicator_callbacks.run_start") as p:
        yield p


@pytest.fixture
def run_end():
    with patch("artemis.external_interaction.communicator_callbacks.run_end") as p:
        yield p


@pytest.fixture
def wait_for_result():
    with patch(
        "artemis.external_interaction.communicator_callbacks.wait_for_result"
    ) as wfr:
        yield wfr


@pytest.fixture
def mock_ispyb_get_time():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.get_current_time_string"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_store_grid_scan():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.store_grid_scan"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_update_time_and_status():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.update_grid_scan_with_end_time_and_status"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_begin_deposition():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.begin_deposition"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_end_deposition():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.end_deposition"
    ) as p:
        yield p


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
        "plan_name": "run_gridscan_and_move",
    }
    test_descriptor_document: dict = {
        "uid": "bd45c2e5-2b85-4280-95d7-a9a15800a78b",
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "name": ISPYB_PLAN_NAME,
    }
    test_event_document: dict = {
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
    test_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "success",
        "reason": "",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
    }
    test_failed_stop_document: dict = {
        "run_start": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
        "time": 1666604300.0310638,
        "uid": "65b2bde5-5740-42d7-9047-e860e06fbe15",
        "exit_status": "fail",
        "reason": "",
        "num_events": {"fake_ispyb_params": 1, "primary": 1},
    }


@pytest.fixture
def td():
    return TestData()
