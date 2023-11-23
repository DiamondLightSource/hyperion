from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.backlight import Backlight
from dodal.devices.fast_grid_scan import GridAxis
from dodal.devices.oav.oav_detector import OAV, OAVConfigParams
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from hyperion.exceptions import WarningException
from hyperion.experiment_plans.oav_grid_detection_plan import (
    OavGridDetectionComposite,
    grid_detection_plan,
)
from hyperion.external_interaction.callbacks.grid_detection_callback import (
    GridDetectionCallback,
)
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)


@pytest.fixture
def fake_devices(smargon: Smargon, backlight: Backlight, test_config_files):
    oav = i03.oav(fake_with_ophyd_sim=True)
    oav.wait_for_connection()

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")

    # fmt: off
    oav.mxsc.bottom.set([0,0,0,0,0,0,0,0,5,5,6,6,7,7,8,8,7,7,6,6])  # noqa: E231
    oav.mxsc.top.set([0,0,0,0,0,0,0,0,5,5,4,4,3,3,2,2,3,3,4,4])  # noqa: E231
    # fmt: on

    oav.mxsc.pin_tip.tip_x.sim_put(8)
    oav.mxsc.pin_tip.tip_y.sim_put(5)

    with patch("dodal.devices.areadetector.plugins.MJPG.requests"), patch(
        "dodal.devices.areadetector.plugins.MJPG.Image"
    ) as mock_image_class:
        mock_image = MagicMock()
        mock_image_class.open.return_value.__enter__.return_value = mock_image

        composite = OavGridDetectionComposite(
            backlight=backlight,
            oav=oav,
            smargon=smargon,
        )

        yield composite, mock_image


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_grid_detection_plan_runs_and_triggers_snapshots(
    bps_wait: MagicMock,
    RE: RunEngine,
    test_config_files,
    fake_devices,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    cb = OavSnapshotCallback()
    RE.subscribe(cb)

    composite, image = fake_devices
    composite.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    composite.oav.parameters.micronsPerXPixel = 1.58
    composite.oav.parameters.micronsPerYPixel = 1.58
    composite.oav.parameters.beam_centre_i = 517
    composite.oav.parameters.beam_centre_j = 350

    RE(
        grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )
    )
    assert image.save.call_count == 6

    assert len(cb.snapshot_filenames) == 2
    assert len(cb.snapshot_filenames[0]) == 3
    assert cb.snapshot_filenames[0][0] == "tmp/test_0.png"
    assert cb.snapshot_filenames[1][2] == "tmp/test_90_grid_overlay.png"

    assert len(cb.out_upper_left) == 2
    assert len(cb.out_upper_left[0]) == 2


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
def test_grid_detection_plan_gives_warningerror_if_tip_not_found(
    RE,
    test_config_files,
    fake_devices,
):
    composite, _ = fake_devices
    oav: OAV = composite.oav
    oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    oav.parameters.micronsPerXPixel = 1.58
    oav.parameters.micronsPerYPixel = 1.58
    oav.parameters.beam_centre_i = 517
    oav.parameters.beam_centre_j = 350
    oav.mxsc.pin_tip.tip_x.sim_put(-1)
    oav.mxsc.pin_tip.tip_y.sim_put(-1)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    with pytest.raises(WarningException) as excinfo:
        RE(
            grid_detection_plan(
                composite,
                parameters=params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )
        )
    assert "No pin found" in excinfo.value.args[0]


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_given_when_grid_detect_then_upper_left_and_start_position_as_expected(
    mock_wait,
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    composite, _ = fake_devices
    composite.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    composite.oav.parameters.micronsPerXPixel = 0.1
    composite.oav.parameters.micronsPerYPixel = 0.1
    composite.oav.parameters.beam_centre_i = 4
    composite.oav.parameters.beam_centre_j = 4

    oav_cb = OavSnapshotCallback()
    grid_param_cb = GridDetectionCallback(composite.oav.parameters, 0.004)
    RE.subscribe(oav_cb)
    RE.subscribe(grid_param_cb)
    RE(
        grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            box_size_microns=0.2,
            grid_width_microns=161.2,
        )
    )

    # 8, 2 based on tip x, and lowest value in the top array
    assert oav_cb.out_upper_left[0] == [8, 2]
    assert oav_cb.out_upper_left[1] == [8, 2]

    gridscan_params = grid_param_cb.get_grid_parameters()

    assert gridscan_params.x_start == pytest.approx(0.0005)
    assert gridscan_params.y1_start == pytest.approx(-0.0001)
    assert gridscan_params.z1_start == pytest.approx(-0.0001)


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_when_grid_detection_plan_run_twice_then_values_do_not_persist_in_callback(
    bps_wait: MagicMock,
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    composite, _ = fake_devices
    composite.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    composite.oav.parameters.micronsPerXPixel = 1.58
    composite.oav.parameters.micronsPerYPixel = 1.58
    composite.oav.parameters.beam_centre_i = 517
    composite.oav.parameters.beam_centre_j = 350

    for _ in range(2):
        cb = OavSnapshotCallback()
        RE.subscribe(cb)

        RE(
            grid_detection_plan(
                composite,
                parameters=params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )
        )
    assert len(cb.snapshot_filenames) == 2
    assert len(cb.out_upper_left) == 2


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_when_grid_detection_plan_run_then_grid_dectection_callback_gets_correct_values(
    bps_wait: MagicMock,
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters("loopCentring", test_config_files["oav_config_json"])

    composite, _ = fake_devices
    composite.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    composite.oav.parameters.micronsPerXPixel = 1.58
    composite.oav.parameters.micronsPerYPixel = 1.58
    composite.oav.parameters.beam_centre_i = 517
    composite.oav.parameters.beam_centre_j = 350

    cb = GridDetectionCallback(composite.oav.parameters, exposure_time=0.5)
    RE.subscribe(cb)

    RE(
        grid_detection_plan(
            composite,
            parameters=params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )
    )

    my_grid_params = cb.get_grid_parameters()

    test_x_grid_axis = GridAxis(
        my_grid_params.x_start, my_grid_params.x_step_size, my_grid_params.x_steps
    )

    test_y_grid_axis = GridAxis(
        my_grid_params.y1_start, my_grid_params.y_step_size, my_grid_params.y_steps
    )

    test_z_grid_axis = GridAxis(
        my_grid_params.z2_start, my_grid_params.z_step_size, my_grid_params.z_steps
    )

    assert my_grid_params.x_start == pytest.approx(-0.7942199999999999)
    assert my_grid_params.y1_start == pytest.approx(-0.53984)
    assert my_grid_params.y2_start == pytest.approx(-0.53984)
    assert my_grid_params.z1_start == pytest.approx(-0.53984)
    assert my_grid_params.z2_start == pytest.approx(-0.53984)
    assert my_grid_params.x_step_size == pytest.approx(0.02)
    assert my_grid_params.y_step_size == pytest.approx(0.02)
    assert my_grid_params.z_step_size == pytest.approx(0.02)
    assert my_grid_params.x_steps == pytest.approx(9)
    assert my_grid_params.y_steps == pytest.approx(1)
    assert my_grid_params.z_steps == pytest.approx(1)
    assert cb.x_step_size_mm == cb.y_step_size_mm == cb.z_step_size_mm == 0.02

    assert my_grid_params.dwell_time_ms == pytest.approx(500)

    assert my_grid_params.x_axis == test_x_grid_axis
    assert my_grid_params.y_axis == test_y_grid_axis
    assert my_grid_params.z_axis == test_z_grid_axis
