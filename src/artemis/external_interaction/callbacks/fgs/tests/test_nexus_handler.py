import copy
from unittest.mock import MagicMock, call, patch

import pytest

from artemis.external_interaction.callbacks.fgs.nexus_callback import (
    FGSNexusFileHandlerCallback,
)
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
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
def nexus_writer():
    with patch(
        "artemis.external_interaction.callbacks.fgs.nexus_callback.NexusWriter"
    ) as nw:
        yield nw


@pytest.fixture
def params_for_first():
    with patch(
        "artemis.external_interaction.callbacks.fgs.nexus_callback.create_parameters_for_first_file"
    ) as p:
        yield p


@pytest.fixture
def params_for_second():
    with patch(
        "artemis.external_interaction.callbacks.fgs.nexus_callback.create_parameters_for_second_file"
    ) as p:
        yield p


def test_writers_setup_on_init(
    params_for_second: MagicMock,
    params_for_first: MagicMock,
    nexus_writer: MagicMock,
):
    params = FGSInternalParameters()
    nexus_handler = FGSNexusFileHandlerCallback(params)
    # flake8 gives an error if we don't do something with communicator
    nexus_handler.__init__(params)

    nexus_writer.assert_has_calls(
        [
            call(params_for_first()),
            call(params_for_second()),
        ],
        any_order=True,
    )


def test_writers_dont_create_on_init(
    params_for_second: MagicMock,
    params_for_first: MagicMock,
    nexus_writer: MagicMock,
):
    params = FGSInternalParameters()
    nexus_handler = FGSNexusFileHandlerCallback(params)

    nexus_handler.nxs_writer_1.create_nexus_file.assert_not_called()
    nexus_handler.nxs_writer_2.create_nexus_file.assert_not_called()


def test_writers_do_create_one_file_each_on_start_doc_for_run_gridscan(
    nexus_writer: MagicMock,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]

    params = FGSInternalParameters()
    nexus_handler = FGSNexusFileHandlerCallback(params)
    nexus_handler.start(test_start_document)

    nexus_handler.nxs_writer_1.create_nexus_file.assert_not_called()
    nexus_handler.nxs_writer_2.create_nexus_file.assert_not_called()

    gridscan_start_doc = copy.deepcopy(test_start_document)
    gridscan_start_doc["subplan_name"] = "run_gridscan"

    nexus_handler.start(gridscan_start_doc)

    nexus_handler.nxs_writer_1.create_nexus_file.assert_called_once()
    nexus_handler.nxs_writer_2.create_nexus_file.assert_called_once()
