import os
from typing import Callable, Sequence
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.DCM import DCM
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from event_model import RunStart
from ophyd.sim import make_fake_device

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_nexus_writer,
    read_hardware_for_zocalo,
)
from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.external_interaction.ispyb.rotation_ispyb_store import (
    StoreRotationInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from unit_tests.conftest import from_file


@pytest.fixture
def params():
    return RotationInternalParameters(
        **from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_outer_start_doc(params: RotationInternalParameters):
    return {
        "subplan_name": CONST.PLAN.ROTATION_OUTER,
        "hyperion_internal_parameters": params.json(),
    }


@pytest.fixture
def test_main_start_doc():
    return {
        "subplan_name": CONST.PLAN.ROTATION_MAIN,
        "zocalo_environment": "dev_zocalo",
    }


def activate_callbacks(cbs: RotationCallbackCollection | XrayCentreCallbackCollection):
    cbs.ispyb_handler.active = True
    cbs.nexus_handler.active = True


def fake_rotation_scan(
    params: RotationInternalParameters,
    subscriptions: RotationCallbackCollection | Sequence[PlanReactiveCallback],
    after_open_do: Callable | None = None,
    after_main_do: Callable | None = None,
):
    attenuator = make_fake_device(Attenuator)(name="attenuator")
    flux = make_fake_device(Flux)(name="flux")
    dcm = make_fake_device(DCM)(
        name="dcm", daq_configuration_path=i03.DAQ_CONFIGURATION_PATH
    )
    dcm.energy_in_kev.user_readback.sim_put(12.1)
    eiger = make_fake_device(EigerDetector)(name="eiger")

    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            "hyperion_internal_parameters": params.json(),
            CONST.TRIGGER.ZOCALO: CONST.PLAN.ROTATION_MAIN,
        }
    )
    def plan():
        if after_open_do:
            after_open_do(subscriptions)

        @bpp.set_run_key_decorator(CONST.PLAN.ROTATION_MAIN)
        @bpp.run_decorator(
            md={
                "subplan_name": CONST.PLAN.ROTATION_MAIN,
                "zocalo_environment": "dev_zocalo",
                "scan_points": [params.get_scan_points()],
            }
        )
        def fake_main_plan():
            yield from read_hardware_for_ispyb_during_collection(attenuator, flux, dcm)
            yield from read_hardware_for_nexus_writer(eiger)
            yield from read_hardware_for_zocalo(eiger)
            if after_main_do:
                after_main_do(subscriptions)
            yield from bps.sleep(0)

        yield from fake_main_plan()

    return plan()


@pytest.fixture
def activated_mocked_cbs():
    cb = RotationCallbackCollection()
    cb.ispyb_handler.emit_cb = MagicMock
    activate_callbacks(cb)
    cb.nexus_handler.activity_gated_event = MagicMock(autospec=True)
    cb.nexus_handler.activity_gated_start = MagicMock(autospec=True)
    return cb


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_nexus_handler_gets_documents_in_mock_plan(
    ispyb,
    RE: RunEngine,
    params: RotationInternalParameters,
    activated_mocked_cbs: RotationCallbackCollection,
):
    nexus_handler = activated_mocked_cbs.nexus_handler
    RE(fake_rotation_scan(params, [nexus_handler]))

    params.hyperion_params.ispyb_params.transmission_fraction = 1.0
    params.hyperion_params.ispyb_params.flux = 10.0

    assert nexus_handler.activity_gated_start.call_count == 2  # type: ignore
    call_content_outer = nexus_handler.activity_gated_start.call_args_list[0].args[0]  # type: ignore
    assert call_content_outer["hyperion_internal_parameters"] == params.json()
    call_content_inner = nexus_handler.activity_gated_start.call_args_list[1].args[0]  # type: ignore
    assert call_content_inner["subplan_name"] == CONST.PLAN.ROTATION_MAIN

    assert nexus_handler.activity_gated_event.call_count == 3  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
def test_nexus_handler_only_writes_once(
    nexus_writer: MagicMock,
    RE: RunEngine,
    params: RotationInternalParameters,
    test_outer_start_doc,
):
    nexus_writer.return_value.full_filename = "test_full_filename"
    cb = RotationNexusFileCallback()
    cb.active = True
    RE(fake_rotation_scan(params, [cb]))
    nexus_writer.assert_called_once()
    assert cb.writer is not None
    cb.writer.create_nexus_file.assert_called_once()  # type: ignore


def test_nexus_handler_triggers_write_file_when_told(
    RE: RunEngine, params: RotationInternalParameters
):
    if os.path.isfile("/tmp/file_name_0.nxs"):
        os.remove("/tmp/file_name_0.nxs")
    if os.path.isfile("/tmp/file_name_0_master.h5"):
        os.remove("/tmp/file_name_0_master.h5")

    cb = RotationNexusFileCallback()
    cb.active = True

    RE(fake_rotation_scan(params, [cb]))

    assert os.path.isfile("/tmp/file_name_0.nxs")
    assert os.path.isfile("/tmp/file_name_0_master.h5")
    os.remove("/tmp/file_name_0.nxs")
    os.remove("/tmp/file_name_0_master.h5")


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_zocalo_start_and_end_not_triggered_if_ispyb_ids_not_present(
    ispyb_store,
    zocalo_trigger,
    nexus_writer,
    RE: RunEngine,
    params: RotationInternalParameters,
    test_outer_start_doc,
):
    nexus_writer.return_value.full_filename = "test_full_filename"
    cb = RotationCallbackCollection()
    activate_callbacks(cb)

    cb.ispyb_handler.ispyb = MagicMock(spec=StoreRotationInIspyb)
    cb.ispyb_handler.params = params
    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_rotation_scan(params, cb))
    cb.ispyb_handler.emit_cb.zocalo_interactor.run_start.assert_not_called()  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb"
)
def test_ispyb_starts_on_opening_and_zocalo_on_main_so_ispyb_triggered_before_zocalo(
    ispyb_store,
    zocalo_trigger,
    nexus_writer,
    RE: RunEngine,
    params: RotationInternalParameters,
    test_outer_start_doc,
    test_main_start_doc,
):
    mock_store_in_ispyb_instance = MagicMock(spec=StoreInIspyb)
    returned_ids = IspybIds(data_collection_group_id=0, data_collection_ids=(0,))
    mock_store_in_ispyb_instance.begin_deposition.return_value = returned_ids
    mock_store_in_ispyb_instance.update_deposition.return_value = returned_ids

    ispyb_store.return_value = mock_store_in_ispyb_instance
    nexus_writer.return_value.full_filename = "test_full_filename"
    cb = RotationCallbackCollection()
    activate_callbacks(cb)
    cb.ispyb_handler.emit_cb.stop = MagicMock()  # type: ignore

    def after_open_do(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.ispyb.begin_deposition.assert_called_once()  # pyright: ignore
        callbacks.ispyb_handler.ispyb.update_deposition.assert_not_called()  # pyright: ignore

    def after_main_do(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.ispyb.update_deposition.assert_called_once()  # pyright: ignore
        cb.ispyb_handler.emit_cb.zocalo_interactor.run_start.assert_called_once()  # type: ignore

    RE(fake_rotation_scan(params, cb, after_open_do, after_main_do))

    cb.ispyb_handler.emit_cb.zocalo_interactor.run_start.assert_called_once()  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
def test_ispyb_handler_grabs_uid_from_main_plan_and_not_first_start_doc(
    zocalo, RE: RunEngine, params: RotationInternalParameters, test_outer_start_doc
):
    cb = RotationCallbackCollection()
    cb.ispyb_handler.emit_cb = None
    activate_callbacks(cb)
    cb.nexus_handler.activity_gated_event = MagicMock(autospec=True)
    cb.nexus_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_start = MagicMock(
        autospec=True, side_effect=cb.ispyb_handler.activity_gated_start
    )

    def after_open_do(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.activity_gated_start.assert_called_once()
        assert callbacks.ispyb_handler.uid_to_finalize_on is None

    def after_main_do(callbacks: RotationCallbackCollection):
        cb.ispyb_handler.ispyb_ids = IspybIds(
            data_collection_ids=(0,), data_collection_group_id=0
        )
        assert callbacks.ispyb_handler.activity_gated_start.call_count == 2
        assert callbacks.ispyb_handler.uid_to_finalize_on is not None

    with patch(
        "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
        autospec=True,
    ):
        RE(fake_rotation_scan(params, cb, after_open_do, after_main_do))


ids = [
    IspybIds(data_collection_group_id=23, data_collection_ids=(45,), grid_ids=None),
    IspybIds(data_collection_group_id=24, data_collection_ids=(48,), grid_ids=None),
    IspybIds(data_collection_group_id=25, data_collection_ids=(51,), grid_ids=None),
    IspybIds(data_collection_group_id=26, data_collection_ids=(111,), grid_ids=None),
    IspybIds(data_collection_group_id=27, data_collection_ids=(238476,), grid_ids=None),
    IspybIds(data_collection_group_id=36, data_collection_ids=(189765,), grid_ids=None),
    IspybIds(data_collection_group_id=39, data_collection_ids=(0,), grid_ids=None),
    IspybIds(data_collection_group_id=43, data_collection_ids=(89,), grid_ids=None),
]


@pytest.mark.parametrize("ispyb_ids", ids)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_ispyb_reuses_dcgid_on_same_sampleID(
    rotation_ispyb: MagicMock,
    RE: RunEngine,
    params: RotationInternalParameters,
    ispyb_ids,
):
    cb = [RotationISPyBCallback()]
    cb[0].active = True
    ispyb_ids = IspybIds(
        data_collection_group_id=23, data_collection_ids=(45,), grid_ids=None
    )
    rotation_ispyb.return_value.begin_deposition.return_value = ispyb_ids

    test_cases = zip(
        ["abc", "abc", "abc", "def", "abc", "def", "def", "xyz", "hij", "hij", "hij"],
        [False, True, True, False, False, False, True, False, False, True, True],
    )

    last_dcgid = None

    for sample_id, same_dcgid in test_cases:
        params.hyperion_params.ispyb_params.sample_id = sample_id

        def after_open_do(callbacks: list[RotationISPyBCallback]):
            assert callbacks[0].uid_to_finalize_on is None

        def after_main_do(callbacks: list[RotationISPyBCallback]):
            assert callbacks[0].uid_to_finalize_on is not None

        RE(fake_rotation_scan(params, cb, after_open_do, after_main_do))

        if same_dcgid:
            assert rotation_ispyb.call_args.args[1] is not None
            assert rotation_ispyb.call_args.args[1] is last_dcgid
        else:
            assert rotation_ispyb.call_args.args[1] is None

        last_dcgid = cb[0].ispyb_ids.data_collection_group_id


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_ispyb_specifies_experiment_type_if_supplied(
    rotation_ispyb: MagicMock,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = [RotationISPyBCallback()]
    cb[0].active = True
    params.hyperion_params.ispyb_params.ispyb_experiment_type = "Characterization"
    rotation_ispyb.return_value.begin_deposition.return_value = IspybIds(
        data_collection_group_id=23, data_collection_ids=(45,), grid_ids=None
    )

    params.hyperion_params.ispyb_params.sample_id = "abc"

    RE(fake_rotation_scan(params, cb))

    assert rotation_ispyb.call_args.args[2] == "Characterization"
    assert rotation_ispyb.call_args.args[1] is None


n_images_store_id = [
    (123, False),
    (3600, True),
    (1800, True),
    (150, False),
    (500, True),
    (201, True),
    (1, False),
    (2000, True),
    (2000, True),
    (2000, True),
    (123, False),
    (3600, True),
    (1800, True),
    (123, False),
    (1800, True),
]


@pytest.mark.parametrize("n_images,store_id", n_images_store_id)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    new=MagicMock(),
)
def test_ispyb_handler_stores_sampleid_for_full_collection_not_screening(
    n_images: int,
    store_id: bool,
    params: RotationInternalParameters,
):
    cb = RotationISPyBCallback()
    cb.active = True

    doc: RunStart = {
        "time": 0,
        "uid": "abc123",
    }

    params.hyperion_params.ispyb_params.sample_id = "SAMPLEID"
    params.experiment_params.rotation_angle = n_images / 10
    assert params.experiment_params.get_num_images() == n_images
    doc["subplan_name"] = CONST.PLAN.ROTATION_OUTER  # type: ignore
    doc["hyperion_internal_parameters"] = params.json()  # type: ignore

    cb.start(doc)
    assert (cb.last_sample_id == "SAMPLEID") is store_id
