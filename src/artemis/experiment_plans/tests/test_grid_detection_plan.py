from unittest.mock import MagicMock, call, patch

import pytest
from dodal.beamlines import i03
from dodal.devices.backlight import Backlight
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon
from ophyd.status import Status

from artemis.exceptions import WarningException
from artemis.experiment_plans.oav_grid_detection_plan import (
    create_devices,
    grid_detection_plan,
)


def fake_create_devices():
    oav = i03.oav(fake_with_ophyd_sim=True)
    oav.wait_for_connection()
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.wait_for_connection()
    bl = i03.backlight(fake_with_ophyd_sim=True)
    bl.wait_for_connection()

    oav.zoom_controller.zrst.set("1.0x")
    oav.zoom_controller.onst.set("2.0x")
    oav.zoom_controller.twst.set("3.0x")
    oav.zoom_controller.thst.set("5.0x")
    oav.zoom_controller.frst.set("7.0x")
    oav.zoom_controller.fvst.set("9.0x")

    # fmt: off
    oav.mxsc.bottom.set([0,0,0,0,0,0,0,0,1,1,1,1,1,2,2,2,2,3,3,3,3,33,3,4,4,4])  # noqa: E231
    oav.mxsc.top.set([7,7,7,7,7,7,6,6,6,6,6,6,2,2,2,2,3,3,3,3,33,3,4,4,4])  # noqa: E231
    # fmt: on

    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False

    return oav, smargon, bl


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.wait")
@patch("bluesky.plan_stubs.mv")
def test_grid_detection_plan_runs_and_triggers_snapshots(
    bps_mv: MagicMock,
    bps_wait: MagicMock,
    RE,
    test_config_files,
):
    oav, smargon, bl = fake_create_devices()

    oav.mxsc.pin_tip.tip_x.sim_put(100)
    oav.mxsc.pin_tip.tip_y.sim_put(100)

    params = OAVParameters(context="loopCentring", **test_config_files)
    gridscan_params = GridScanParams()

    finished_status = Status(done=True, success=True)
    oav.snapshot.trigger = MagicMock(return_value=finished_status)

    RE(
        grid_detection_plan(
            parameters=params,
            out_parameters=gridscan_params,
            snapshot_dir="tmp",
            out_snapshot_filenames=[],
            out_upper_left={},
            snapshot_template="test_{angle}",
        )
    )
    oav.snapshot.trigger.assert_called()


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("bluesky.plan_stubs.mv")
def test_grid_detection_plan_gives_warningerror_if_tip_not_found(
    bps_mv: MagicMock,
    RE,
    test_config_files,
):
    oav: OAV
    oav, smargon, bl = fake_create_devices()
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
                out_snapshot_filenames=[],
                out_upper_left={},
                snapshot_template="test_{angle}",
            )
        )
    assert "No pin found" in excinfo.value.args[0]


@patch("dodal.beamlines.i03.device_instantiation")
def test_create_devices(create_device: MagicMock):
    create_devices()
    create_device.assert_has_calls(
        [
            call(Smargon, "smargon", "-MO-SGON-01:", True, False),
            call(OAV, "oav", "-DI-OAV-01:", True, False),
            call(
                device=Backlight,
                name="backlight",
                prefix="-EA-BL-01:",
                wait=True,
                fake=False,
            ),
        ],
        any_order=True,
    )
