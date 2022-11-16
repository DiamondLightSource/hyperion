from unittest.mock import patch

import pytest


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
    ) as wfr:
        yield wfr


@pytest.fixture
def mock_ispyb_store_grid_scan():
    with patch(
        "artemis.external_interaction.communicator_callbacks.StoreInIspyb3D.store_grid_scan"
    ) as wfr:
        yield wfr
