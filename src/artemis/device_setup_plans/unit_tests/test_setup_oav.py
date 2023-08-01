from unittest.mock import MagicMock

import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from ophyd.signal import Signal
from ophyd.status import Status

from artemis.device_setup_plans.setup_oav import pre_centring_setup_oav

ZOOM_LEVELS_XML = (
    "src/artemis/experiment_plans/tests/test_data/jCameraManZoomLevels.xml"
)
OAV_CENTRING_JSON = "src/artemis/experiment_plans/tests/test_data/OAVCentring.json"
DISPLAY_CONFIGURATION = (
    "src/artemis/experiment_plans/tests/test_data/display.configuration"
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
