from unittest.mock import patch

import pytest

from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
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
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_update_time_and_status():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb._update_scan_with_end_time_and_status"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_begin_deposition():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb.begin_deposition"
    ) as p:
        yield p


@pytest.fixture
def mock_ispyb_end_deposition():
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb.end_deposition"
    ) as p:
        yield p


@pytest.fixture
def ispyb_handler():
    return GridscanISPyBCallback()
