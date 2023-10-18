from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.parameters.constants import ISPYB_PLAN_NAME
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

test_start_document = {
    "uid": "d8bee3ee-f614-4e7a-a516-25d6b9e87ef3",
    "time": 1666604299.6149616,
    "versions": {"ophyd": "1.6.4.post76+g0895f9f", "bluesky": "1.8.3"},
    "scan_id": 1,
    "plan_type": "generator",
    "plan_name": "run_gridscan_and_move",
}


@pytest.fixture
def dummy_params():
    return GridscanInternalParameters(**default_raw_params())


@pytest.fixture
def nexus_writer():
    with patch("hyperion.external_interaction.nexus.write_nexus.NexusWriter") as nw:
        yield nw


def test_writers_not_setup_on_plan_start_doc(
    nexus_writer: MagicMock,
    dummy_params: GridscanInternalParameters,
):
    nexus_handler = GridscanNexusFileCallback()
    nexus_writer.assert_not_called()
    nexus_handler.start(
        {
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": dummy_params.json(),
        }
    )
    nexus_writer.assert_not_called()


def test_writers_dont_create_on_init_but_do_on_ispyb_event(
    nexus_writer: MagicMock,
    dummy_params: GridscanInternalParameters,
):
    nexus_handler = GridscanNexusFileCallback()

    assert nexus_handler.nexus_writer_1 is None
    assert nexus_handler.nexus_writer_2 is None

    nexus_handler.start(
        {
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": dummy_params.json(),
        }
    )

    assert nexus_handler.nexus_writer_1 is None
    assert nexus_handler.nexus_writer_2 is None

    mock_writer = MagicMock()

    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter",
        mock_writer,
    ):
        nexus_handler.descriptor({"name": ISPYB_PLAN_NAME})

    assert nexus_handler.nexus_writer_1 is not None
    assert nexus_handler.nexus_writer_2 is not None
    nexus_handler.nexus_writer_1.create_nexus_file.assert_called()
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called()


def test_writers_do_create_one_file_each_on_start_doc_for_run_gridscan(
    nexus_writer: MagicMock, dummy_params
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]

    nexus_handler = GridscanNexusFileCallback()
    nexus_handler.start(
        {
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": dummy_params.json(),
        }
    )
    nexus_handler.start(
        {
            "subplan_name": "run_gridscan",
        }
    )
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter"
    ):
        nexus_handler.descriptor(
            {
                "name": "ispyb_readings",
            }
        )

    nexus_handler.nexus_writer_1.create_nexus_file.assert_called()
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called()


def test_sensible_error_if_writing_triggered_before_params_received(
    nexus_writer: MagicMock, dummy_params
):
    nexus_handler = GridscanNexusFileCallback()
    with pytest.raises(AssertionError) as excinfo:
        nexus_handler.descriptor(
            {
                "name": "ispyb_readings",
            }
        )

    assert "Nexus callback did not receive parameters" in excinfo.value.args[0]
