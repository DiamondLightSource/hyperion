import os
from typing import Callable
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
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
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
from hyperion.parameters.constants import ROTATION_OUTER_PLAN, ROTATION_PLAN_MAIN
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def params():
    return RotationInternalParameters(
        **from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_start_doc(params: RotationInternalParameters):
    return {
        "subplan_name": ROTATION_OUTER_PLAN,
        "hyperion_internal_parameters": params.json(),
    }


def activate_callbacks(cbs: RotationCallbackCollection | XrayCentreCallbackCollection):
    cbs.ispyb_handler.active = True
    cbs.nexus_handler.active = True
    cbs.zocalo_handler.active = True


def fake_rotation_scan(
    params: RotationInternalParameters,
    subscriptions: RotationCallbackCollection | list[RotationISPyBCallback],
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
            "subplan_name": ROTATION_OUTER_PLAN,
            "hyperion_internal_parameters": params.json(),
        }
    )
    def plan():
        if after_open_do:
            after_open_do(subscriptions)

        @bpp.set_run_key_decorator(ROTATION_PLAN_MAIN)
        @bpp.run_decorator(
            md={
                "subplan_name": ROTATION_PLAN_MAIN,
            }
        )
        def fake_main_plan():
            yield from read_hardware_for_ispyb_during_collection(attenuator, flux, dcm)
            yield from read_hardware_for_nexus_writer(eiger)
            if after_main_do:
                after_main_do(subscriptions)
            yield from bps.sleep(0)

        yield from fake_main_plan()

    return plan()


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_nexus_handler_gets_documents_in_mock_plan(
    ispyb, RE: RunEngine, params: RotationInternalParameters
):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationISPyBCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.setup()
        activate_callbacks(cb)
        cb.nexus_handler.activity_gated_event = MagicMock(autospec=True)
        cb.nexus_handler.activity_gated_start = MagicMock(autospec=True)
        cb.ispyb_handler.activity_gated_start = MagicMock(autospec=True)
        cb.ispyb_handler.activity_gated_stop = MagicMock(autospec=True)

    RE(fake_rotation_scan(params, cb))

    params.hyperion_params.ispyb_params.transmission_fraction = 1.0
    params.hyperion_params.ispyb_params.flux = 10.0

    assert cb.nexus_handler.activity_gated_start.call_count == 2
    call_content_outer = cb.nexus_handler.activity_gated_start.call_args_list[0].args[0]
    assert call_content_outer["hyperion_internal_parameters"] == params.json()
    call_content_inner = cb.nexus_handler.activity_gated_start.call_args_list[1].args[0]
    assert call_content_inner["subplan_name"] == ROTATION_PLAN_MAIN

    assert cb.nexus_handler.activity_gated_event.call_count == 2


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_nexus_handler_only_writes_once(
    ispyb,
    nexus_writer: MagicMock,
    RE: RunEngine,
    params: RotationInternalParameters,
    test_start_doc,
):
    nexus_writer.return_value.full_filename = "test_full_filename"
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.setup()
    activate_callbacks(cb)
    cb.ispyb_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_event = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_stop = MagicMock(autospec=True)

    RE(fake_rotation_scan(params, cb))
    nexus_writer.assert_called_once()
    assert cb.nexus_handler.writer is not None
    cb.nexus_handler.writer.create_nexus_file.assert_called_once()


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_nexus_handler_triggers_write_file_when_told(
    ispyb, RE: RunEngine, params: RotationInternalParameters
):
    if os.path.isfile("/tmp/file_name_0.nxs"):
        os.remove("/tmp/file_name_0.nxs")
    if os.path.isfile("/tmp/file_name_0_master.h5"):
        os.remove("/tmp/file_name_0_master.h5")

    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        cb = RotationCallbackCollection.setup()
    activate_callbacks(cb)
    cb.ispyb_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_stop = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb = ispyb
    cb.ispyb_handler.params = params

    RE(fake_rotation_scan(params, cb))

    assert os.path.isfile("/tmp/file_name_0.nxs")
    assert os.path.isfile("/tmp/file_name_0_master.h5")
    os.remove("/tmp/file_name_0.nxs")
    os.remove("/tmp/file_name_0_master.h5")


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
    autospec=True,
)
def test_zocalo_start_and_end_triggered_once(
    ispyb,
    zocalo: MagicMock,
    RE: RunEngine,
    params: RotationInternalParameters,
):
    cb = RotationCallbackCollection.setup()
    activate_callbacks(cb)
    cb.nexus_handler.activity_gated_start = MagicMock(autospec=True)
    cb.nexus_handler.activity_gated_event = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_stop = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb = MagicMock(spec=StoreRotationInIspyb)
    cb.ispyb_handler.params = params

    def set_ispyb_ids(cbs):
        cbs.ispyb_handler.ispyb_ids = IspybIds(
            data_collection_ids=0, data_collection_group_id=0
        )

    RE(fake_rotation_scan(params, cb, after_main_do=set_ispyb_ids))

    zocalo.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_start.assert_called_once()
    cb.zocalo_handler.zocalo_interactor.run_end.assert_called_once()


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
def test_zocalo_start_and_end_not_triggered_if_ispyb_ids_not_present(
    zocalo, RE: RunEngine, params: RotationInternalParameters, test_start_doc
):
    cb = RotationCallbackCollection.setup()
    activate_callbacks(cb)
    cb.nexus_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_start = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_stop = MagicMock(autospec=True)
    cb.ispyb_handler.activity_gated_event = MagicMock(autospec=True)
    cb.ispyb_handler.ispyb = MagicMock(spec=StoreRotationInIspyb)
    cb.ispyb_handler.params = params
    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_rotation_scan(params, cb))


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb"
)
def test_zocalo_starts_on_opening_and_ispyb_on_main_so_ispyb_triggered_before_zocalo(
    mock_store_in_ispyb_class,
    zocalo,
    nexus_writer,
    RE: RunEngine,
    params: RotationInternalParameters,
    test_start_doc,
):
    mock_store_in_ispyb_instance = MagicMock(spec=StoreInIspyb)
    mock_store_in_ispyb_instance.begin_deposition.return_value = IspybIds(
        data_collection_group_id=0, data_collection_ids=0
    )
    mock_store_in_ispyb_instance.update_deposition.return_value = IspybIds(
        data_collection_group_id=0, data_collection_ids=0
    )
    mock_store_in_ispyb_class.return_value = mock_store_in_ispyb_instance
    nexus_writer.return_value.full_filename = "test_full_filename"
    cb = RotationCallbackCollection.setup()
    activate_callbacks(cb)
    cb.nexus_handler.activity_gated_start(test_start_doc)
    cb.zocalo_handler.activity_gated_start(test_start_doc)

    cb.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    cb.zocalo_handler.zocalo_interactor.run_end = MagicMock()

    def after_open_do(callbacks: RotationCallbackCollection):
        callbacks.ispyb_handler.ispyb.begin_deposition.assert_called_once()  # pyright: ignore
        callbacks.ispyb_handler.ispyb.update_deposition.assert_not_called()  # pyright: ignore

    def after_main_do(callbacks: RotationCallbackCollection):
        # cb.ispyb_handler.ispyb_ids = IspybIds(
        #     data_collection_ids=0, data_collection_group_id=0
        # )
        callbacks.ispyb_handler.ispyb.update_deposition.assert_called_once()  # pyright: ignore
        cb.zocalo_handler.zocalo_interactor.run_end.assert_not_called()  # pyright: ignore

    RE(fake_rotation_scan(params, cb, after_open_do, after_main_do))

    cb.zocalo_handler.zocalo_interactor.run_end.assert_called_once()


@patch(
    "hyperion.external_interaction.callbacks.rotation.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
def test_ispyb_handler_grabs_uid_from_main_plan_and_not_first_start_doc(
    zocalo, RE: RunEngine, params: RotationInternalParameters, test_start_doc
):
    cb = RotationCallbackCollection.setup()
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
            data_collection_ids=0, data_collection_group_id=0
        )
        assert callbacks.ispyb_handler.activity_gated_start.call_count == 2
        assert callbacks.ispyb_handler.uid_to_finalize_on is not None

    with patch(
        "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreRotationInIspyb",
        autospec=True,
    ):
        RE(fake_rotation_scan(params, cb, after_open_do, after_main_do))


ids = [
    IspybIds(data_collection_group_id=23, data_collection_ids=45, grid_ids=None),
    IspybIds(data_collection_group_id=24, data_collection_ids=48, grid_ids=None),
    IspybIds(data_collection_group_id=25, data_collection_ids=51, grid_ids=None),
    IspybIds(data_collection_group_id=26, data_collection_ids=111, grid_ids=None),
    IspybIds(data_collection_group_id=27, data_collection_ids=238476, grid_ids=None),
    IspybIds(data_collection_group_id=36, data_collection_ids=189765, grid_ids=None),
    IspybIds(data_collection_group_id=39, data_collection_ids=0, grid_ids=None),
    IspybIds(data_collection_group_id=43, data_collection_ids=89, grid_ids=None),
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
    doc["subplan_name"] = ROTATION_OUTER_PLAN  # type: ignore
    doc["hyperion_internal_parameters"] = params.json()  # type: ignore

    cb.start(doc)
    assert (cb.last_sample_id == "SAMPLEID") is store_id
