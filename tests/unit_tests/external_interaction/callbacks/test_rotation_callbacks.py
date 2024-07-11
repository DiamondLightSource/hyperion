import os
from typing import Callable, Sequence, Tuple
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from event_model import RunStart
from ophyd.sim import make_fake_device
from ophyd_async.core import DeviceCollector, set_mock_value

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_nexus_writer,
    read_hardware_for_zocalo,
)
from hyperion.external_interaction.callbacks.common.callback_util import (
    create_rotation_callbacks,
)
from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.data_model import (
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.components import IspybExperimentType
from hyperion.parameters.constants import CONST
from hyperion.parameters.rotation import RotationScan
from hyperion.utils.aperturescatterguard import (
    load_default_aperture_scatterguard_positions_if_unset,
)

from ....conftest import raw_params_from_file


@pytest.fixture
def params():
    return RotationScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_outer_start_doc(params: RotationScan):
    return {
        "subplan_name": CONST.PLAN.ROTATION_OUTER,
        "hyperion_parameters": params.json(),
    }


@pytest.fixture
def test_main_start_doc():
    return {
        "subplan_name": CONST.PLAN.ROTATION_MAIN,
        "zocalo_environment": "dev_zocalo",
    }


def activate_callbacks(cbs: Tuple[RotationNexusFileCallback, RotationISPyBCallback]):
    cbs[1].active = True
    cbs[0].active = True


def fake_rotation_scan(
    params: RotationScan,
    subscriptions: (
        Tuple[RotationNexusFileCallback, RotationISPyBCallback]
        | Sequence[PlanReactiveCallback]
    ),
    after_open_do: Callable | None = None,
    after_main_do: Callable | None = None,
):
    with DeviceCollector(mock=True):
        attenuator = Attenuator("", "attenuator")
    flux = make_fake_device(Flux)(name="flux")
    eiger = make_fake_device(EigerDetector)(name="eiger")
    dcm = i03.dcm(fake_with_ophyd_sim=True)
    ap_sg = i03.aperture_scatterguard(fake_with_ophyd_sim=True)
    load_default_aperture_scatterguard_positions_if_unset(ap_sg)
    set_mock_value(dcm.energy_in_kev.user_readback, 12.1)

    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("rotation_scan_with_cleanup_and_subs")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.ROTATION_OUTER,
            "hyperion_parameters": params.json(),
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
                "scan_points": [params.scan_points],
            }
        )
        def fake_main_plan():
            yield from read_hardware_for_ispyb_during_collection(
                ap_sg, attenuator, flux, dcm
            )
            yield from read_hardware_for_nexus_writer(eiger)
            yield from read_hardware_for_zocalo(eiger)
            if after_main_do:
                after_main_do(subscriptions)
            yield from bps.sleep(0)

        yield from fake_main_plan()

    return plan()


@pytest.fixture
def activated_mocked_cbs():
    nexus_callback, ispyb_callback = create_rotation_callbacks()
    ispyb_callback.emit_cb = MagicMock
    activate_callbacks((nexus_callback, ispyb_callback))
    nexus_callback.activity_gated_event = MagicMock(autospec=True)
    nexus_callback.activity_gated_start = MagicMock(autospec=True)
    return nexus_callback, ispyb_callback


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb",
    autospec=True,
)
def test_nexus_handler_gets_documents_in_mock_plan(
    ispyb,
    RE: RunEngine,
    params: RotationScan,
    activated_mocked_cbs: Tuple[RotationNexusFileCallback, RotationISPyBCallback],
):
    nexus_handler, _ = activated_mocked_cbs
    RE(fake_rotation_scan(params, [nexus_handler]))

    assert nexus_handler.activity_gated_start.call_count == 2  # type: ignore
    call_content_outer = nexus_handler.activity_gated_start.call_args_list[0].args[0]  # type: ignore
    assert call_content_outer["hyperion_parameters"] == params.json()
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
    params: RotationScan,
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
    RE: RunEngine, params: RotationScan
):
    pattern = f"{params.storage_directory}{params.file_name}_{params.detector_params.run_number}"
    files = [f"{pattern}.nxs", f"{pattern}_master.h5"]

    def do_files(do_assert=False):
        for file in files:
            if do_assert:
                assert os.path.isfile(file)
            if os.path.isfile(file):
                os.remove(file)

    do_files()
    cb = RotationNexusFileCallback()
    cb.active = True
    RE(fake_rotation_scan(params, [cb]))
    do_files(do_assert=True)


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb",
    autospec=True,
)
def test_zocalo_start_and_end_not_triggered_if_ispyb_ids_not_present(
    ispyb_store,
    zocalo_trigger,
    nexus_writer,
    RE: RunEngine,
    params: RotationScan,
    test_outer_start_doc,
):
    nexus_writer.return_value.full_filename = "test_full_filename"
    nexus_callback, ispyb_callback = create_rotation_callbacks()
    activate_callbacks((nexus_callback, ispyb_callback))

    ispyb_callback.ispyb = MagicMock(spec=StoreInIspyb)
    ispyb_callback.params = params
    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_rotation_scan(params, (nexus_callback, ispyb_callback)))
    ispyb_callback.emit_cb.zocalo_interactor.run_start.assert_not_called()  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
@patch("hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb")
def test_ispyb_starts_on_opening_and_zocalo_on_main_so_ispyb_triggered_before_zocalo(
    ispyb_store,
    zocalo_trigger,
    nexus_writer,
    RE: RunEngine,
    params: RotationScan,
    test_outer_start_doc,
    test_main_start_doc,
):
    mock_store_in_ispyb_instance = MagicMock(spec=StoreInIspyb)
    returned_ids = IspybIds(data_collection_group_id=0, data_collection_ids=(0,))
    mock_store_in_ispyb_instance.begin_deposition.return_value = returned_ids
    mock_store_in_ispyb_instance.update_deposition.return_value = returned_ids

    ispyb_store.return_value = mock_store_in_ispyb_instance
    nexus_writer.return_value.full_filename = "test_full_filename"
    nexus_callback, ispyb_callback = create_rotation_callbacks()
    activate_callbacks((nexus_callback, ispyb_callback))
    ispyb_callback.emit_cb.stop = MagicMock()  # type: ignore

    def after_open_do(
        callbacks: Tuple[RotationNexusFileCallback, RotationISPyBCallback],
    ):
        ispyb_callback.ispyb.begin_deposition.assert_called_once()  # pyright: ignore
        ispyb_callback.ispyb.update_deposition.assert_not_called()  # pyright: ignore

    def after_main_do(
        callbacks: Tuple[RotationNexusFileCallback, RotationISPyBCallback],
    ):
        ispyb_callback.ispyb.update_deposition.assert_called_once()  # pyright: ignore
        ispyb_callback.emit_cb.zocalo_interactor.run_start.assert_called_once()  # type: ignore

    RE(
        fake_rotation_scan(
            params, (nexus_callback, ispyb_callback), after_open_do, after_main_do
        )
    )

    ispyb_callback.emit_cb.zocalo_interactor.run_start.assert_called_once()  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
def test_ispyb_handler_grabs_uid_from_main_plan_and_not_first_start_doc(
    zocalo, RE: RunEngine, params: RotationScan, test_outer_start_doc
):
    (nexus_callback, ispyb_callback) = create_rotation_callbacks()
    ispyb_callback.emit_cb = None
    activate_callbacks((nexus_callback, ispyb_callback))
    nexus_callback.activity_gated_event = MagicMock(autospec=True)
    nexus_callback.activity_gated_start = MagicMock(autospec=True)
    ispyb_callback.activity_gated_start = MagicMock(
        autospec=True, side_effect=ispyb_callback.activity_gated_start
    )

    def after_open_do(
        callbacks: Tuple[RotationNexusFileCallback, RotationISPyBCallback],
    ):
        ispyb_callback.activity_gated_start.assert_called_once()  # type: ignore
        assert ispyb_callback.uid_to_finalize_on is None

    def after_main_do(
        callbacks: Tuple[RotationNexusFileCallback, RotationISPyBCallback],
    ):
        ispyb_callback.ispyb_ids = IspybIds(
            data_collection_ids=(0,), data_collection_group_id=0
        )
        assert ispyb_callback.activity_gated_start.call_count == 2  # type: ignore
        assert ispyb_callback.uid_to_finalize_on is not None

    with patch(
        "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb",
        autospec=True,
    ):
        RE(
            fake_rotation_scan(
                params, (nexus_callback, ispyb_callback), after_open_do, after_main_do
            )
        )


@patch(
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb",
    autospec=True,
)
def test_ispyb_reuses_dcgid_on_same_sampleID(
    rotation_ispyb: MagicMock,
    RE: RunEngine,
    params: RotationScan,
):
    ispyb_cb = RotationISPyBCallback()
    ispyb_cb.active = True
    ispyb_ids = IspybIds(data_collection_group_id=23, data_collection_ids=(45,))
    rotation_ispyb.return_value.begin_deposition.return_value = ispyb_ids

    test_cases = zip(
        [123, 123, 123, 456, 123, 456, 456, 999, 789, 789, 789],
        [False, True, True, False, False, False, True, False, False, True, True],
    )

    last_dcgid = None

    for sample_id, same_dcgid in test_cases:
        params.sample_id = sample_id

        def after_open_do(callbacks: list[RotationISPyBCallback]):
            assert callbacks[0].uid_to_finalize_on is None

        def after_main_do(callbacks: list[RotationISPyBCallback]):
            assert callbacks[0].uid_to_finalize_on is not None

        RE(fake_rotation_scan(params, [ispyb_cb], after_open_do, after_main_do))

        begin_deposition_scan_data: ScanDataInfo = (
            rotation_ispyb.return_value.begin_deposition.call_args.args[1][0]
        )
        if same_dcgid:
            assert begin_deposition_scan_data.data_collection_info.parent_id is not None
            assert (
                begin_deposition_scan_data.data_collection_info.parent_id is last_dcgid
            )
        else:
            assert begin_deposition_scan_data.data_collection_info.parent_id is None

        last_dcgid = ispyb_cb.ispyb_ids.data_collection_group_id


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
    "hyperion.external_interaction.callbacks.rotation.ispyb_callback.StoreInIspyb",
    new=MagicMock(),
)
def test_ispyb_handler_stores_sampleid_for_full_collection_not_screening(
    n_images: int,
    store_id: bool,
    params: RotationScan,
):
    cb = RotationISPyBCallback()
    cb.active = True

    doc: RunStart = {
        "time": 0,
        "uid": "abc123",
    }

    params.sample_id = 987678
    params.scan_width_deg = n_images / 10
    if n_images < 200:
        params.ispyb_experiment_type = IspybExperimentType.CHARACTERIZATION
    assert params.num_images == n_images
    doc["subplan_name"] = CONST.PLAN.ROTATION_OUTER  # type: ignore
    doc["hyperion_parameters"] = params.json()  # type: ignore

    cb.start(doc)
    assert (cb.last_sample_id == 987678) is store_id
