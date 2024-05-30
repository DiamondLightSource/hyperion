from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.common.exceptions import WarningException
from dodal.devices.oav.oav_detector import OAV, OAVConfigParams
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.oav.pin_image_recognition.utils import SampleLocation
from dodal.devices.oav.utils import (
    get_move_required_so_that_beam_is_at_pixel,
    wait_for_tip_to_be_found,
)
from dodal.devices.smargon import Smargon
from ophyd.signal import Signal
from ophyd.sim import instantiate_fake_device
from ophyd.status import Status

from hyperion.device_setup_plans.setup_oav import (
    pre_centring_setup_oav,
)

ZOOM_LEVELS_XML = "tests/test_data/test_jCameraManZoomLevels.xml"
OAV_CENTRING_JSON = "tests/test_data/test_OAVCentring.json"
DISPLAY_CONFIGURATION = "tests/test_data/test_display.configuration"


@pytest.fixture
def oav() -> OAV:
    oav = i03.oav(fake_with_ophyd_sim=True)
    oav.parameters = OAVConfigParams(ZOOM_LEVELS_XML, DISPLAY_CONFIGURATION)

    oav.proc.port_name.sim_put("proc")  # type: ignore
    oav.cam.port_name.sim_put("CAM")  # type: ignore

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")
    return oav


@pytest.fixture
def mock_parameters():
    return OAVParameters("loopCentring", OAV_CENTRING_JSON)


def fake_smargon() -> Smargon:
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False

    def mock_set(motor, val):
        motor.user_readback.sim_put(val)  # type: ignore
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
    zoom,
    expected_plugin,
    mock_parameters: OAVParameters,
    oav: OAV,
    ophyd_pin_tip_detection: PinTipDetection,
):
    mock_parameters.zoom = zoom

    RE = RunEngine()
    RE(pre_centring_setup_oav(oav, mock_parameters, ophyd_pin_tip_detection))
    assert oav.grid_snapshot.input_plugin.get() == expected_plugin


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
    oav: OAV,
    px_per_um,
    beam_centre,
    angle,
    pixel_to_move_to,
    expected_xyz,
):
    oav.parameters.micronsPerXPixel = px_per_um[0]
    oav.parameters.micronsPerYPixel = px_per_um[1]
    oav.parameters.beam_centre_i = beam_centre[0]
    oav.parameters.beam_centre_j = beam_centre[1]

    smargon.omega.user_readback.sim_put(angle)  # type: ignore

    RE = RunEngine(call_returns_result=True)
    pos = RE(
        get_move_required_so_that_beam_is_at_pixel(
            smargon, pixel_to_move_to, oav.parameters
        )
    ).plan_result

    assert pos == pytest.approx(expected_xyz)


def test_when_set_up_oav_then_only_waits_on_oav_to_finish(
    mock_parameters: OAVParameters, oav: OAV, ophyd_pin_tip_detection: PinTipDetection
):
    """This test will hang if pre_centring_setup_oav waits too generally as my_waiting_device
    never finishes moving"""
    my_waiting_device = Signal(name="")
    my_waiting_device.set = MagicMock(return_value=Status())

    def my_plan():
        yield from bps.abs_set(my_waiting_device, 10, wait=False)
        yield from pre_centring_setup_oav(oav, mock_parameters, ophyd_pin_tip_detection)

    RE = RunEngine()
    RE(my_plan())


@pytest.mark.asyncio
async def test_given_tip_found_when_wait_for_tip_to_be_found_called_then_tip_immediately_returned():
    mock_pin_tip_detect: PinTipDetection = instantiate_fake_device(
        PinTipDetection, name="pin_detect"
    )
    await mock_pin_tip_detect.connect(mock=True)
    mock_pin_tip_detect._get_tip_and_edge_data = AsyncMock(
        return_value=SampleLocation(100, 100, np.array([]), np.array([]))
    )
    RE = RunEngine(call_returns_result=True)
    result = RE(wait_for_tip_to_be_found(mock_pin_tip_detect))
    assert result.plan_result == (100, 100)  # type: ignore
    mock_pin_tip_detect._get_tip_and_edge_data.assert_called_once()


@pytest.mark.asyncio
async def test_given_no_tip_when_wait_for_tip_to_be_found_called_then_exception_thrown():
    mock_pin_tip_detect: PinTipDetection = instantiate_fake_device(
        PinTipDetection, name="pin_detect"
    )
    await mock_pin_tip_detect.connect(mock=True)
    await mock_pin_tip_detect.validity_timeout.set(0.2)
    mock_pin_tip_detect._get_tip_and_edge_data = AsyncMock(
        return_value=SampleLocation(
            *PinTipDetection.INVALID_POSITION, np.array([]), np.array([])
        )
    )
    RE = RunEngine(call_returns_result=True)
    with pytest.raises(WarningException):
        RE(wait_for_tip_to_be_found(mock_pin_tip_detect))
