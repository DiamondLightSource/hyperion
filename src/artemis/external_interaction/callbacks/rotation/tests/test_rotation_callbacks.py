import os
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.parameters.external_parameters import from_file
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def params():
    return RotationInternalParameters(
        **from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def RE():
    return RunEngine({})


def fake_get_plan(
    parameters: RotationInternalParameters,
    subscriptions: RotationCallbackCollection,
):
    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "rotation_scan_with_cleanup",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    def plan():
        @bpp.set_run_key_decorator("rotation_scan_main")
        @bpp.run_decorator(
            md={
                "subplan_name": "rotation_scan_main",
            }
        )
        def fake_main_plan():
            yield from bps.sleep(0)

        yield from fake_main_plan()

    return plan()


def test_nexus_handler_gets_documents_in_mock_plan(
    RE: RunEngine, params: RotationInternalParameters
):
    with patch(
        "artemis.external_interaction.callbacks.rotation.rotation_callback_collection.RotationZocaloHandlerCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)
    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.nexus_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_get_plan(params, cb))

    assert cb.nexus_handler.start.call_count == 2
    call_content_outer = cb.nexus_handler.start.call_args_list[0].args[0]
    assert call_content_outer["hyperion_internal_parameters"] == params.json()
    call_content_inner = cb.nexus_handler.start.call_args_list[1].args[0]
    assert call_content_inner["subplan_name"] == "rotation_scan_main"
    assert cb.nexus_handler.stop.call_count == 2


@patch(
    "artemis.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
def test_nexus_handler_only_writes_once(
    nexus_writer, RE: RunEngine, params: RotationInternalParameters
):
    with patch(
        "artemis.external_interaction.callbacks.rotation.rotation_callback_collection.RotationZocaloHandlerCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_get_plan(params, cb))
    nexus_writer.assert_called_once()
    cb.nexus_handler.writer.create_nexus_file.assert_called_once()


def test_nexus_handler_triggers_write_file_when_told(
    RE: RunEngine,
    params: RotationInternalParameters,
):
    if os.path.isfile("/tmp/file_name_0.nxs"):
        os.remove("/tmp/file_name_0.nxs")
    if os.path.isfile("/tmp/file_name_0_master.h5"):
        os.remove("/tmp/file_name_0_master.h5")

    with patch(
        "artemis.external_interaction.callbacks.rotation.rotation_callback_collection.RotationZocaloHandlerCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)

    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_get_plan(params, cb))

    assert os.path.isfile("/tmp/file_name_0.nxs")
    assert os.path.isfile("/tmp/file_name_0_master.h5")
    os.remove("/tmp/file_name_0.nxs")
    os.remove("/tmp/file_name_0_master.h5")


@patch(
    "artemis.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_zocalo_start_and_end_triggered_once(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)

    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.nexus_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb_ids = [0]

    RE(fake_get_plan(params, cb))

    zocalo.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_start.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_end.assert_called_once()


@patch(
    "artemis.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_zocalo_start_and_end_not_triggered_if_ispyb_ids_not_present(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)

    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.nexus_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)
    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_get_plan(params, cb))
