from functools import partial
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.synchrotron import SynchrotronMode
from dodal.devices.zocalo import ZocaloResults, ZocaloTrigger
from event_model import Event
from ophyd.sim import make_fake_device
from ophyd_async.core.async_status import AsyncStatus

from hyperion.external_interaction.callbacks.common.callback_util import (
    create_gridscan_callbacks,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan


def make_event_doc(data, descriptor="abc123") -> Event:
    return {
        "time": 0,
        "timestamps": {"a": 0},
        "seq_num": 0,
        "uid": "not so random uid",
        "descriptor": descriptor,
        "data": data,
    }


BASIC_PRE_SETUP_DOC = {
    "undulator_current_gap": 0,
    "synchrotron-synchrotron_mode": SynchrotronMode.USER,
    "s4_slit_gaps_xgap": 0,
    "s4_slit_gaps_ygap": 0,
    "robot-barcode": "BARCODE",
}

BASIC_POST_SETUP_DOC = {
    "attenuator_actual_transmission": 0,
    "flux_flux_reading": 10,
    "dcm_energy_in_kev": 11.105,
}


def mock_zocalo_trigger(zocalo: ZocaloResults, result):
    @AsyncStatus.wrap
    async def mock_complete(results):
        await zocalo._put_results(results, {"dcid": 0, "dcgid": 0})

    zocalo.trigger = MagicMock(side_effect=partial(mock_complete, result))


def run_generic_ispyb_handler_setup(
    ispyb_handler: GridscanISPyBCallback,
    params: ThreeDGridScan,
):
    """This is useful when testing 'run_gridscan_and_move(...)' because this stuff
    happens at the start of the outer plan."""

    ispyb_handler.active = True
    ispyb_handler.activity_gated_start(
        {
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            "hyperion_internal_parameters": params.old_parameters().json(),
        }  # type: ignore
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "123abc", "name": CONST.DESCRIPTORS.ISPYB_HARDWARE_READ}  # type: ignore
    )
    ispyb_handler.activity_gated_event(
        make_event_doc(
            BASIC_PRE_SETUP_DOC,
            descriptor="123abc",
        )
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "abc123", "name": CONST.DESCRIPTORS.ISPYB_TRANSMISSION_FLUX_READ}  # type: ignore
    )
    ispyb_handler.activity_gated_event(
        make_event_doc(
            BASIC_POST_SETUP_DOC,
            descriptor="abc123",
        )
    )


def modified_interactor_mock(assign_run_end: Callable | None = None):
    mock = MagicMock(spec=ZocaloTrigger)
    if assign_run_end:
        mock.run_end = assign_run_end
    return mock


def modified_store_grid_scan_mock(*args, dcids=(0, 0), dcgid=0, **kwargs):
    mock = MagicMock(spec=StoreInIspyb)
    mock.begin_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid
    )
    mock.update_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid, grid_ids=(0, 0)
    )
    return mock


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    with (
        patch(
            "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
            modified_interactor_mock,
        ),
        patch(
            "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb.append_to_comment"
        ),
        patch(
            "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb.begin_deposition",
            new=MagicMock(
                return_value=IspybIds(
                    data_collection_ids=(0, 0), data_collection_group_id=0
                )
            ),
        ),
        patch(
            "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb.update_deposition",
            new=MagicMock(
                return_value=IspybIds(
                    data_collection_ids=(0, 0),
                    data_collection_group_id=0,
                    grid_ids=(0, 0),
                )
            ),
        ),
    ):
        nexus_callback, ispyb_callback = create_gridscan_callbacks()
        ispyb_callback.ispyb = MagicMock(spec=StoreInIspyb)

    return (nexus_callback, ispyb_callback)


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


@pytest.fixture
def simple_beamline(detector_motion, oav, smargon, synchrotron, test_config_files, dcm):
    magic_mock = MagicMock(autospec=True)
    magic_mock.oav = oav
    magic_mock.smargon = smargon
    magic_mock.detector_motion = detector_motion
    magic_mock.zocalo = make_fake_device(ZocaloResults)()
    magic_mock.dcm = dcm
    scan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")
    magic_mock.fast_grid_scan = scan
    magic_mock.synchrotron = synchrotron
    oav.zoom_controller.frst.set("7.5x")
    oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    oav.parameters.update_on_zoom(7.5, 1024, 768)
    return magic_mock


def assert_event(mock_call, expected):
    actual = mock_call.args[0]
    if "data" in actual:
        actual = actual["data"]
    for k, v in expected.items():
        assert actual[k] == v, f"Mismatch in key {k}, {actual} <=> {expected}"
