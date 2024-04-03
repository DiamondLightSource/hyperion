from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)

from ..conftest import TestData


@pytest.fixture
def nexus_writer():
    with patch("hyperion.external_interaction.nexus.write_nexus.NexusWriter") as nw:
        yield nw


def test_writers_not_setup_on_plan_start_doc(
    nexus_writer: MagicMock,
):
    nexus_handler = GridscanNexusFileCallback()
    nexus_writer.assert_not_called()
    nexus_handler.activity_gated_start(TestData.test_start_document)
    nexus_writer.assert_not_called()


@patch("hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter")
def test_writers_dont_create_on_init_but_do_on_ispyb_event(
    mock_nexus_writer: MagicMock,
):
    nexus_handler = GridscanNexusFileCallback()

    assert nexus_handler.nexus_writer_1 is None
    assert nexus_handler.nexus_writer_2 is None

    nexus_handler.activity_gated_start(TestData.test_start_document)
    nexus_handler.activity_gated_descriptor(
        TestData.test_descriptor_document_during_data_collection
    )
    nexus_handler.activity_gated_event(
        TestData.test_event_document_during_data_collection
    )

    assert nexus_handler.nexus_writer_1 is not None
    assert nexus_handler.nexus_writer_2 is not None
    nexus_handler.nexus_writer_1.create_nexus_file.assert_called()
    nexus_handler.nexus_writer_2.create_nexus_file.assert_called()


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
