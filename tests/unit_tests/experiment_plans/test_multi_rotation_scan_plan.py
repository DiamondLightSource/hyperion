from __future__ import annotations

from itertools import takewhile

from dodal.devices.synchrotron import SynchrotronMode
from ophyd_async.core import set_mock_value

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    calculate_motion_profile,
    multi_rotation_scan,
)
from hyperion.parameters.rotation import MultiRotationScan

from ...conftest import RunEngineSimulator

TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def test_multi_rotation_scan_params(test_multi_rotation_params: MultiRotationScan):
    for scan in test_multi_rotation_params.single_rotation_scans:
        assert isinstance(scan.omega_start_deg, float)


def test_multi_rotation_plan_runs_multiple_plans_in_one_arm(
    fake_create_rotation_devices: RotationScanComposite,
    test_multi_rotation_params: MultiRotationScan,
    sim_run_engine_for_rotation: RunEngineSimulator,
):
    omega = fake_create_rotation_devices.smargon.omega
    set_mock_value(
        fake_create_rotation_devices.synchrotron.synchrotron_mode, SynchrotronMode.USER
    )
    msgs = sim_run_engine_for_rotation.simulate_plan(
        multi_rotation_scan(fake_create_rotation_devices, test_multi_rotation_params)
    )

    msgs = sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "stage" and msg.obj.name == "eiger"
    )[1:]

    msgs_within_arming = list(
        takewhile(
            lambda msg: msg.command != "unstage"
            and (not msg.obj or msg.obj.name != "eiger"),
            msgs,
        )
    )

    def _assert_set_seq_and_return_remaining(remaining, name_value_pairs):
        for name, value in name_value_pairs:
            try:
                remaining = (
                    sim_run_engine_for_rotation.assert_message_and_return_remaining(
                        remaining,
                        lambda msg: msg.command == "set"
                        and msg.obj.name == name
                        and msg.args == (value,),
                    )
                )
            except Exception as e:
                raise Exception(f"Failed to find {name} being set to {value}") from e
        return remaining

    for scan in test_multi_rotation_params.single_rotation_scans:
        motion_values = calculate_motion_profile(
            scan, int(omega.acceleration.get()), int(omega.max_velocity.get())
        )
        msgs_within_arming = _assert_set_seq_and_return_remaining(
            msgs_within_arming,
            [
                ("smargon_x", scan.x_start_um),
                ("smargon_y", scan.y_start_um),
                ("smargon_z", scan.z_start_um),
                ("smargon_phi", scan.phi_start_deg),
                ("smargon_chi", scan.chi_start_deg),
            ],
        )
        msgs_within_arming = (
            sim_run_engine_for_rotation.assert_message_and_return_remaining(
                msgs_within_arming,
                lambda msg: msg.command == "set" and msg.obj.name == "zebra-pc-arm",
            )
        )
        msgs_within_arming = (
            sim_run_engine_for_rotation.assert_message_and_return_remaining(
                msgs_within_arming,
                lambda msg: msg.command == "set"
                and msg.obj.name == "smargon_omega"
                and msg.args
                == (
                    (scan.scan_width_deg + motion_values.shutter_opening_deg)
                    * motion_values.direction.multiplier,
                ),
            )
        )
