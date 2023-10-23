import os
from tkinter import S
from typing import Callable
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.attenuator import Attenuator
from dodal.devices.flux import Flux
from ophyd.sim import make_fake_device

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.store_in_ispyb import StoreInIspyb
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def params():
    return RotationInternalParameters(
        **from_file(
            "src/hyperion/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def RE():
    return RunEngine({})


def fake_rotation_scan(
    parameters: RotationInternalParameters,
    subscriptions: RotationCallbackCollection,
    after_open_assert: Callable | None = None,
    after_main_assert: Callable | None = None,
):
    attenuator = make_fake_device(Attenuator)(name="attenuator")
    flux = make_fake_device(Flux)(name="flux")

    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "rotation_scan_with_cleanup",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    def plan():
        if after_open_assert:
            after_open_assert(subscriptions)

        @bpp.set_run_key_decorator("rotation_scan_main")
        @bpp.run_decorator(
            md={
                "subplan_name": "rotation_scan_main",
            }
        )
        def fake_main_plan():
            yield from read_hardware_for_ispyb_during_collection(attenuator, flux)
            if after_main_assert:
                after_main_assert(subscriptions)
            yield from bps.sleep(0)

        yield from fake_main_plan()

    return plan()


def test_nexus_handler_gets_documents_in_mock_plan(
    RE: RunEngine, params: RotationInternalParameters
):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)
    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_rotation_scan(params, cb))

    params.hyperion_params.ispyb_params.transmission_fraction = 1.0
    params.hyperion_params.ispyb_params.flux = 10.0

    assert cb.nexus_handler.start.call_count == 2
    call_content_outer = cb.nexus_handler.start.call_args_list[0].args[0]
    assert call_content_outer["hyperion_internal_parameters"] == params.json()
    call_content_inner = cb.nexus_handler.start.call_args_list[1].args[0]
    assert call_content_inner["subplan_name"] == "rotation_scan_main"


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
def test_nexus_handler_only_writes_once(
    nexus_writer, RE: RunEngine, params: RotationInternalParameters
):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_rotation_scan(params, cb))
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
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.from_params(params)

    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)

    RE(fake_rotation_scan(params, cb))

    assert os.path.isfile("/tmp/file_name_0.nxs")
    assert os.path.isfile("/tmp/file_name_0_master.h5")
    os.remove("/tmp/file_name_0.nxs")
    os.remove("/tmp/file_name_0_master.h5")


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_zocalo_start_and_end_triggered_once(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)

    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb_ids = (0, 0)

    RE(fake_rotation_scan(params, cb))

    zocalo.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_start.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_end.assert_called_once()


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_zocalo_start_and_end_not_triggered_if_ispyb_ids_not_present(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)

    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.stop = MagicMock(autospec=True)
    cb.ispyb_handler.event = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb = MagicMock(autospec=True)
    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_rotation_scan(params, cb))


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_zocalo_starts_on_opening_and_ispyb_on_main_so_ispyb_triggered_before_zocalo(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)
    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb = MagicMock(spec=StoreInIspyb)
    cb.ispyb_handler.ispyb_ids = (0, 0)
    cb.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    cb.zocalo_handler.zocalo_interactor.run_end = MagicMock()

    def after_open_assert(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.ispyb.begin_deposition.assert_not_called()

    def after_main_assert(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.ispyb.begin_deposition.assert_called_once()
        cb.zocalo_handler.zocalo_interactor.run_end.assert_not_called()

    RE(fake_rotation_scan(params, cb, after_open_assert, after_main_assert))

    cb.zocalo_handler.zocalo_interactor.run_end.assert_called_once()


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloInteractor",
    autospec=True,
)
def test_ispyb_handler_grabs_uid_from_main_plan_and_not_first_start_doc(
    zocalo,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.from_params(params)
    cb.nexus_handler.start = MagicMock(autospec=True)
    cb.ispyb_handler.start = MagicMock(
        autospec=True, side_effect=cb.ispyb_handler.start
    )
    cb.ispyb_handler.ispyb = MagicMock(spec=StoreInIspyb)
    cb.ispyb_handler.ispyb_ids = (0, 0)
    cb.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    cb.zocalo_handler.zocalo_interactor.run_end = MagicMock()

    def after_open_assert(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.start.assert_called_once()
        assert callbacks.ispyb_handler.uid_to_finalize_on is None

    def after_main_assert(callbacks: RotationCallbackCollection):
        assert callbacks.ispyb_handler.start.call_count == 2
        assert callbacks.ispyb_handler.uid_to_finalize_on is not None

    RE(fake_rotation_scan(params, cb, after_open_assert, after_main_assert))
