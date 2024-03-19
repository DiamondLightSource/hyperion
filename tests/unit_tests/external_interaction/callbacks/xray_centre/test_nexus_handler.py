from copy import deepcopy
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from numpy.typing import DTypeLike

from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)

from ..conftest import TestData


@pytest.fixture
def nexus_writer():
    with patch("hyperion.external_interaction.nexus.write_nexus.NexusWriter") as nw:
        yield nw


def test_writers_not_sDTypeLikeetup_on_plan_start_doc(
    nexus_writer: MagicMock,
):
    nexus_handler = GridscanNexusFileCallback()
    nexus_writer.assert_not_called()
    nexus_handler.activity_gated_start(TestData.test_start_document)
    nexus_writer.assert_not_called()


@patch("hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter")
def test_writers_dont_create_on_init_but_do_on_nexus_read_event(
    mock_nexus_writer: MagicMock,
):
    mock_nexus_writer.side_effect = [MagicMock(), MagicMock()]
    nexus_handler = GridscanNexusFileCallback()

    assert nexus_handler.nexus_writer_1 is None
    assert nexus_handler.nexus_writer_2 is None

    nexus_handler.activity_gated_start(TestData.test_gridscan_outer_start_document)
    nexus_handler.activity_gated_descriptor(
        TestData.test_descriptor_document_nexus_read
    )

    nexus_handler.activity_gated_event(TestData.test_event_document_nexus_read)

    assert nexus_handler.nexus_writer_1 is not None
    assert nexus_handler.nexus_writer_2 is not None
    nexus_handler.nexus_writer_1.create_nexus_file.assert_called_once()
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called_once()


@pytest.mark.parametrize(
    ["bit_depth", "vds_type"],
    [
        (8, np.uint8),
        (16, np.uint16),
        (32, np.uint32),
    ],
)
@patch("hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter")
def test_given_different_bit_depths_then_writers_created_wth_correct_VDS_size(
    mock_nexus_writer: MagicMock,
    bit_depth: int,
    vds_type: DTypeLike,
):
    mock_nexus_writer.side_effect = [MagicMock(), MagicMock()]
    nexus_handler = GridscanNexusFileCallback()

    nexus_handler.activity_gated_start(TestData.test_start_document)
    nexus_handler.activity_gated_descriptor(
        TestData.test_descriptor_document_nexus_read
    )
    event_doc = deepcopy(TestData.test_event_document_nexus_read)
    event_doc["data"]["eiger_bit_depth"] = bit_depth

    nexus_handler.activity_gated_event(event_doc)

    assert nexus_handler.nexus_writer_1 is not None
    assert nexus_handler.nexus_writer_2 is not None
    nexus_handler.nexus_writer_1.create_nexus_file.assert_called_once_with(  # type:ignore
        vds_type
    )
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called_once_with(  # type:ignore
        vds_type
    )


@patch("hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter")
def test_beam_and_attenuator_set_on_ispyb_transmission_event(
    mock_nexus_writer: MagicMock,
):
    mock_nexus_writer.side_effect = [MagicMock(), MagicMock()]
    nexus_handler = GridscanNexusFileCallback()

    nexus_handler.activity_gated_start(TestData.test_start_document)
    nexus_handler.activity_gated_descriptor(
        TestData.test_descriptor_document_during_data_collection
    )
    nexus_handler.activity_gated_event(
        TestData.test_event_document_during_data_collection
    )

    for writer in [nexus_handler.nexus_writer_1, nexus_handler.nexus_writer_2]:
        assert writer is not None
        assert writer.attenuator is not None
        assert writer.beam is not None


def test_sensible_error_if_writing_triggered_before_params_received(
    nexus_writer: MagicMock,
):
    nexus_handler = GridscanNexusFileCallback()
    with pytest.raises(AssertionError) as excinfo:
        nexus_handler.activity_gated_descriptor(
            TestData.test_descriptor_document_during_data_collection
        )
        nexus_handler.activity_gated_event(
            TestData.test_event_document_during_data_collection
        )

    assert "Nexus callback did not receive start doc" in excinfo.value.args[0]
