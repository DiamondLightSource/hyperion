from functools import partial
from unittest.mock import MagicMock, patch

import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon
from ophyd.signal import Signal
from ophyd.status import Status

from hyperion.device_setup_plans.setup_oav import (
    get_move_required_so_that_beam_is_at_pixel,
    pre_centring_setup_oav,
)

ZOOM_LEVELS_XML = (
    "src/hyperion/experiment_plans/tests/test_data/jCameraManZoomLevels.xml"
)
OAV_CENTRING_JSON = "src/hyperion/experiment_plans/tests/test_data/OAVCentring.json"
DISPLAY_CONFIGURATION = (
    "src/hyperion/experiment_plans/tests/test_data/display.configuration"
)


@pytest.fixture
def oav() -> OAV:
    oav = i03.oav(fake_with_ophyd_sim=True)

    oav.proc.port_name.sim_put("proc")
    oav.cam.port_name.sim_put("CAM")

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")
    return oav


@pytest.fixture
def mock_parameters():
    return OAVParameters(
        "loopCentring", ZOOM_LEVELS_XML, OAV_CENTRING_JSON, DISPLAY_CONFIGURATION
    )


def fake_smargon() -> Smargon:
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False

    def mock_set(motor, val):
        motor.user_readback.sim_put(val)
        return Status(done=True, success=True)

    def patch_motor(motor):
        return patch.object(motor, "set", partial(mock_set, motor))

    with patch_motor(smargon.omega), patch_motor(smargon.x), patch_motor(
        smargon.y
    ), patch_motor(smargon.z):
        return smargon


@pytest.fixture
def smargon():
    yield fake_smargon()


@pytest.mark.parametrize(
    "zoom, expected_plugin",
    [
        ("1.0", "proc"),
        ("7.0", "CAM"),
    ],
)
def test_when_set_up_oav_with_different_zoom_levels_then_flat_field_applied_correctly(
    zoom, expected_plugin, mock_parameters: OAVParameters, oav: OAV
):
    mock_parameters.zoom = zoom

    RE = RunEngine()
    RE(pre_centring_setup_oav(oav, mock_parameters))
    assert oav.mxsc.input_plugin.get() == expected_plugin
    assert oav.snapshot.input_plugin.get() == "OAV.MXSC"


@pytest.mark.parametrize(
    "px_per_um, beam_centre, angle, pixel_to_move_to, expected_xyz",
    [
        # Simple case of beam being in the top left and each pixel being 1 mm
        ([1000, 1000], [0, 0], 0, [100, 190], [100, 190, 0]),
        ([1000, 1000], [0, 0], -90, [50, 250], [50, 0, 250]),
        ([1000, 1000], [0, 0], 90, [-60, 450], [-60, 0, -450]),
        # Beam offset
        ([1000, 1000], [100, 100], 0, [100, 100], [0, 0, 0]),
        ([1000, 1000], [100, 100], -90, [50, 250], [-50, 0, 150]),
        # Pixels_per_micron different
        ([10, 50], [0, 0], 0, [100, 190], [1, 9.5, 0]),
        ([60, 80], [0, 0], -90, [50, 250], [3, 0, 20]),
    ],
)
def test_values_for_move_so_that_beam_is_at_pixel(
    smargon: Smargon,
    mock_parameters,
    px_per_um,
    beam_centre,
    angle,
    pixel_to_move_to,
    expected_xyz,
):
    mock_parameters.micronsPerXPixel = px_per_um[0]
    mock_parameters.micronsPerYPixel = px_per_um[1]
    mock_parameters.beam_centre_i = beam_centre[0]
    mock_parameters.beam_centre_j = beam_centre[1]

    smargon.omega.user_readback.sim_put(angle)

    RE = RunEngine(call_returns_result=True)
    pos = RE(
        get_move_required_so_that_beam_is_at_pixel(
            smargon, pixel_to_move_to, mock_parameters
        )
    ).plan_result

    assert pos == pytest.approx(expected_xyz)


def test_when_set_up_oav_then_only_waits_on_oav_to_finish(
    mock_parameters: OAVParameters, oav: OAV
):
    """This test will hang if pre_centring_setup_oav waits too generally as my_waiting_device
    never finishes moving"""
    my_waiting_device = Signal(name="")
    my_waiting_device.set = MagicMock(return_value=Status())

    def my_plan():
        yield from bps.abs_set(my_waiting_device, 10, wait=False)
        yield from pre_centring_setup_oav(oav, mock_parameters)

    RE = RunEngine()
    RE(my_plan())
