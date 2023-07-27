import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.oav.oav_parameters import OAVParameters

from artemis.device_setup_plans.setup_oav import pre_centring_setup_oav

ZOOM_LEVELS_XML = (
    "src/artemis/experiment_plans/tests/test_data/jCameraManZoomLevels.xml"
)
OAV_CENTRING_JSON = "src/artemis/experiment_plans/tests/test_data/OAVCentring.json"
DISPLAY_CONFIGURATION = (
    "src/artemis/experiment_plans/tests/test_data/display.configuration"
)


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
    zoom, expected_plugin, mock_parameters: OAVParameters
):
    oav = i03.oav(fake_with_ophyd_sim=True)

    oav.proc.port_name.sim_put("proc")
    oav.cam.port_name.sim_put("CAM")

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")

    mock_parameters.zoom = zoom

    RE = RunEngine()
    RE(pre_centring_setup_oav(oav, mock_parameters))
    assert oav.mxsc.input_plugin.get() == expected_plugin
    assert oav.snapshot.input_plugin.get() == "OAV.MXSC"
