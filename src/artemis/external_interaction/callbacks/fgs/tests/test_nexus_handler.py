from unittest.mock import MagicMock, call, patch

import pytest

from artemis.external_interaction.callbacks.fgs.nexus_callback import (
    FGSNexusFileHandlerCallback,
)
from artemis.parameters.constants import ISPYB_PLAN_NAME
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters

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
    return FGSInternalParameters(**default_raw_params())


@pytest.fixture
def nexus_writer():
    with patch("artemis.external_interaction.nexus.write_nexus.FGSNexusWriter") as nw:
        yield nw


@pytest.fixture
def params_for_first():
    with patch(
        "artemis.external_interaction.nexus.write_nexus.create_parameters_for_first_gridscan_file",
        return_value=(MagicMock(), {}),
    ) as p:
        yield p


@pytest.fixture
def params_for_second():
    with patch(
        "artemis.external_interaction.nexus.write_nexus.create_parameters_for_second_gridscan_file",
        return_value=(MagicMock(), {}),
    ) as p:
        yield p


def test_writers_not_setup_on_plan_start_doc(
    params_for_second: MagicMock,
    params_for_first: MagicMock,
    nexus_writer: MagicMock,
    dummy_params: FGSInternalParameters,
):
    nexus_handler = FGSNexusFileHandlerCallback()
    nexus_writer.assert_not_called()
    nexus_handler.start(
        {
            "subplan_name": "run_gridscan_move_and_tidy",
            "hyperion_internal_parameters": dummy_params.json(),
        }
    )
    nexus_writer.assert_not_called()


def test_writers_dont_create_on_init_but_do_on_ispyb_event(
    params_for_second: MagicMock,
    params_for_first: MagicMock,
    nexus_writer: MagicMock,
    dummy_params: FGSInternalParameters,
):
    nexus_handler = FGSNexusFileHandlerCallback()

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

    nexus_handler.descriptor({"name": ISPYB_PLAN_NAME})

    assert nexus_handler.nexus_writer_1 is not None
    assert nexus_handler.nexus_writer_2 is not None
    nexus_handler.nexus_writer_1.create_nexus_file.assert_called_with(*params_for_first)
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called_with(
        *params_for_second
    )


def test_writers_do_create_one_file_each_on_start_doc_for_run_gridscan(
    nexus_writer: MagicMock, dummy_params
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]

    nexus_handler = FGSNexusFileHandlerCallback()
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
    nexus_handler.descriptor(
        {
            "name": "ispyb_readings",
        }
    )

    nexus_handler.nexus_writer_1.create_nexus_file.assert_called()
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called()
