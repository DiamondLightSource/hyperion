from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.devices.fast_grid_scan import FastGridScan
from ophyd.sim import make_fake_device

from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.ispyb.store_in_ispyb import (
    IspybIds,
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN

from ...system_tests.external_interaction.conftest import TEST_RESULT_LARGE
from ...unit_tests.conftest import RunEngineSimulator


def modified_interactor_mock(assign_run_end: Callable | None = None):
    mock = MagicMock(spec=ZocaloInteractor)
    mock.wait_for_result.return_value = TEST_RESULT_LARGE
    if assign_run_end:
        mock.run_end = assign_run_end
    return mock


def modified_store_grid_scan_mock(*args, dcids=(0, 0), dcgid=0, **kwargs):
    mock = MagicMock(spec=Store3DGridscanInIspyb)
    mock.begin_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid, grid_ids=(0, 0)
    )
    return mock


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.zocalo_callback.ZocaloInteractor",
        modified_interactor_mock,
    ):
        subscriptions = XrayCentreCallbackCollection.setup()
        start_doc = {
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": test_fgs_params.json(),
        }
        subscriptions.ispyb_handler.activity_gated_start(start_doc)
        subscriptions.zocalo_handler.activity_gated_start(start_doc)
    subscriptions.ispyb_handler.ispyb = MagicMock(spec=Store3DGridscanInIspyb)
    subscriptions.ispyb_handler.ispyb.begin_deposition = lambda: IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0, 0)
    )

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
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        subscriptions = RotationCallbackCollection.setup()
    return subscriptions


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


@pytest.fixture
def simple_beamline(detector_motion, oav, smargon, synchrotron):
    magic_mock = MagicMock()
    magic_mock.oav = oav
    magic_mock.smargon = smargon
    magic_mock.detector_motion = detector_motion
    scan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")
    magic_mock.fast_grid_scan = scan
    magic_mock.synchrotron = synchrotron
    oav.zoom_controller.frst.set("7.5x")
    return magic_mock


def add_simple_pin_tip_centre_handlers(sim: RunEngineSimulator):
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


def add_simple_oav_mxsc_callback_handlers(sim: RunEngineSimulator):
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
