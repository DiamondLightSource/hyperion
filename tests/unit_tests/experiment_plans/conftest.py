from functools import partial
from typing import Callable, Union
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.zocalo import ZocaloResults, ZocaloTrigger
from event_model import Event
from ophyd.sim import make_fake_device
from ophyd_async.core.async_status import AsyncStatus

from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandAGridscanInternalParameters,
)


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
    "undulator_gap": 0,
    "synchrotron_machine_status_synchrotron_mode": 0,
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
    params: Union[GridscanInternalParameters, PandAGridscanInternalParameters],
):
    """This is useful when testing 'run_gridscan_and_move(...)' because this stuff
    happens at the start of the outer plan."""

    ispyb_handler.active = True
    ispyb_handler.activity_gated_start(
        {
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            "hyperion_internal_parameters": params.json(),
        }  # type: ignore
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "123abc", "name": CONST.PLAN.ISPYB_HARDWARE_READ}  # type: ignore
    )
    ispyb_handler.activity_gated_event(
        make_event_doc(
            BASIC_PRE_SETUP_DOC,
            descriptor="123abc",
        )
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "abc123", "name": CONST.PLAN.ISPYB_TRANSMISSION_FLUX_READ}  # type: ignore
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
    mock = MagicMock(spec=Store3DGridscanInIspyb)
    mock.begin_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid
    )
    mock.update_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid, grid_ids=(0, 0)
    )
    return mock


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    with patch(
        "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
        modified_interactor_mock,
    ), patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.append_to_comment"
    ), patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.begin_deposition",
        new=MagicMock(
            return_value=IspybIds(
                data_collection_ids=(0, 0), data_collection_group_id=0
            )
        ),
    ), patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.update_deposition",
        new=MagicMock(
            return_value=IspybIds(
                data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0, 0)
            )
        ),
    ):
        subscriptions = XrayCentreCallbackCollection.setup()
        subscriptions.ispyb_handler.ispyb = MagicMock(spec=Store3DGridscanInIspyb)
        start_doc = {
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            "hyperion_internal_parameters": test_fgs_params.json(),
        }
        subscriptions.ispyb_handler.activity_gated_start(start_doc)  # type: ignore
        subscriptions.zocalo_handler.activity_gated_start(start_doc)  # type: ignore

    return subscriptions


@pytest.fixture
def mock_rotation_subscriptions(test_rotation_params):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationNexusFileCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationISPyBCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.ZocaloCallback",
        autospec=True,
    ):
        subscriptions = RotationCallbackCollection.setup()
    return subscriptions


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


def add_simple_pin_tip_centre_handlers(sim):
    """Handlers to simulate a basic fake pin tip"""
    sim.add_handler(
        ("trigger", "read"),
        "oav_mxsc_pin_tip",
        lambda msg: {"oav_mxsc_pin_tip_triggered_tip": {"value": (100, 100)}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_top",
        lambda msg: {"values": {"value": [50, 51, 52, 53, 54, 55]}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_bottom",
        lambda msg: {"values": {"value": [50, 49, 48, 47, 46, 45]}},
    )


def add_simple_oav_mxsc_callback_handlers(sim):
    """Handlers to simulate a basic oav callback firing"""
    sim.add_handler(
        "set",
        "oav_mxsc_enable_callbacks",
        # XXX what are reasonable values for these?
        lambda msg: sim.fire_callback(
            "event",
            {
                "data": {
                    "oav_snapshot_last_saved_path": "/tmp/image1.png",
                    "oav_snapshot_last_path_outer": "/tmp/image2.png",
                    "oav_snapshot_last_path_full_overlay": "/tmp/image3.png",
                    "oav_snapshot_top_left_x": 0,
                    "oav_snapshot_top_left_y": 0,
                    "oav_snapshot_box_width": 100,
                    "smargon_omega": 1,
                    "smargon_x": 0,
                    "smargon_y": 0,
                    "smargon_z": 0,
                    "oav_snapshot_num_boxes_x": 10,
                    "oav_snapshot_num_boxes_y": 10,
                }
            },
        ),
    )
