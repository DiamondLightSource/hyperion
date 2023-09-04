from unittest.mock import MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.backlight import Backlight
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from hyperion.exceptions import WarningException
from hyperion.experiment_plans.oav_grid_detection_plan import (
    create_devices,
    grid_detection_plan,
)
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)


@pytest.fixture
def fake_devices(smargon: Smargon, backlight: Backlight):
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
        mock_image_class.open.return_value = mock_image
        yield oav, smargon, backlight, mock_image


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_grid_detection_plan_runs_and_triggers_snapshots(
    bps_wait: MagicMock,
    RE: RunEngine,
    test_config_files,
    fake_devices,
):
    params = OAVParameters(context="loopCentring", **test_config_files)
    gridscan_params = GridScanParams()

    cb = OavSnapshotCallback()
    RE.subscribe(cb)

    RE(
        grid_detection_plan(
            parameters=params,
            out_parameters=gridscan_params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            grid_width_microns=161.2,
        )
    )
    assert fake_devices[3].save.call_count == 6

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
    oav: OAV = fake_devices[0]
    oav.mxsc.pin_tip.tip_x.sim_put(-1)
    oav.mxsc.pin_tip.tip_y.sim_put(-1)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)
    params = OAVParameters(context="loopCentring", **test_config_files)
    gridscan_params = GridScanParams()
    with pytest.raises(WarningException) as excinfo:
        RE(
            grid_detection_plan(
                parameters=params,
                out_parameters=gridscan_params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )
        )
    assert "No pin found" in excinfo.value.args[0]


@patch("dodal.beamlines.i03.device_instantiation", autospec=True)
def test_create_devices(create_device: MagicMock):
    create_devices()
    create_device.assert_has_calls(
        [
            call(Smargon, "smargon", "-MO-SGON-01:", True, False),
            call(OAV, "oav", "", True, False),
            call(
                Backlight,
                name="backlight",
                prefix="",
                wait=True,
                fake=False,
            ),
        ],
        any_order=True,
    )


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_given_when_grid_detect_then_upper_left_and_start_position_as_expected(
    mock_wait,
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters(context="loopCentring", **test_config_files)
    params.micronsPerXPixel = 0.1
    params.micronsPerYPixel = 0.1
    params.beam_centre_i = 4
    params.beam_centre_j = 4
    gridscan_params = GridScanParams()

    cb = OavSnapshotCallback()
    RE.subscribe(cb)

    RE(
        grid_detection_plan(
            parameters=params,
            out_parameters=gridscan_params,
            snapshot_dir="tmp",
            snapshot_template="test_{angle}",
            box_size_microns=0.2,
            grid_width_microns=161.2,
        )
    )

    # 8, 2 based on tip x, and lowest value in the top array
    assert cb.out_upper_left[0] == [8, 2]
    assert cb.out_upper_left[1] == [8, 2]

    assert gridscan_params.x_start == 0.0005
    assert gridscan_params.y1_start == -0.0001
    assert gridscan_params.z1_start == -0.0001


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
def test_when_grid_detection_plan_run_twice_then_values_do_not_persist_in_callback(
    bps_wait: MagicMock,
    fake_devices,
    RE: RunEngine,
    test_config_files,
):
    params = OAVParameters(context="loopCentring", **test_config_files)
    gridscan_params = GridScanParams()

    for _ in range(2):
        cb = OavSnapshotCallback()
        RE.subscribe(cb)

        RE(
            grid_detection_plan(
                parameters=params,
                out_parameters=gridscan_params,
                snapshot_dir="tmp",
                snapshot_template="test_{angle}",
                grid_width_microns=161.2,
            )
        )
    assert len(cb.snapshot_filenames) == 2
    assert len(cb.out_upper_left) == 2
