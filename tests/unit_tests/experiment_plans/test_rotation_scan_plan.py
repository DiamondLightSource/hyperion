from __future__ import annotations

from itertools import takewhile
from unittest.mock import MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from dodal.devices.backlight import BacklightPosition
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import SynchrotronMode
from dodal.devices.zebra import Zebra
from ophyd_async.core import get_mock_put

from hyperion.experiment_plans.oav_snapshot_plan import (
    OAV_SNAPSHOT_GROUP,
    OAV_SNAPSHOT_SETUP_GROUP,
)
from hyperion.experiment_plans.rotation_scan_plan import (
    RotationMotionProfile,
    RotationScanComposite,
    calculate_motion_profile,
    rotation_scan,
    rotation_scan_plan,
)
from hyperion.parameters.constants import CONST, DocDescriptorNames
from hyperion.parameters.rotation import RotationScan

from ...conftest import RunEngineSimulator
from .conftest import fake_read

TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def do_rotation_main_plan_for_tests(
    run_eng: RunEngine,
    expt_params: RotationScan,
    devices: RotationScanComposite,
    motion_values: RotationMotionProfile,
):
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        run_eng(
            rotation_scan_plan(devices, expt_params, motion_values),
        )


@pytest.fixture
def run_full_rotation_plan(
    RE: RunEngine,
    test_rotation_params: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    oav_parameters_for_rotation,
) -> RotationScanComposite:
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        RE(
            rotation_scan(
                fake_create_rotation_devices,
                test_rotation_params,
                oav_parameters_for_rotation,
            ),
        )
        return fake_create_rotation_devices


@pytest.fixture
def motion_values(test_rotation_params: RotationScan):
    return calculate_motion_profile(
        test_rotation_params,
        0.005,  # time for acceleration
        222,
    )


def setup_and_run_rotation_plan_for_tests(
    RE: RunEngine,
    test_params: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    with patch("bluesky.plan_stubs.wait", autospec=True):
        do_rotation_main_plan_for_tests(
            RE, test_params, fake_create_rotation_devices, motion_values
        )

    return {
        "RE_with_subs": RE,
        "test_rotation_params": test_params,
        "smargon": fake_create_rotation_devices.smargon,
        "zebra": fake_create_rotation_devices.zebra,
    }


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_standard(
    RE: RunEngine,
    test_rotation_params: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    return setup_and_run_rotation_plan_for_tests(
        RE, test_rotation_params, fake_create_rotation_devices, motion_values
    )


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_nomove(
    RE: RunEngine,
    test_rotation_params_nomove: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    return setup_and_run_rotation_plan_for_tests(
        RE, test_rotation_params_nomove, fake_create_rotation_devices, motion_values
    )


def test_rotation_scan_calculations(test_rotation_params: RotationScan):
    test_rotation_params.exposure_time_s = 0.2
    test_rotation_params.omega_start_deg = 10

    motion_values = calculate_motion_profile(
        test_rotation_params,
        0.005,  # time for acceleration
        224,
    )

    assert motion_values.direction == "Negative"
    assert motion_values.start_scan_deg == 10

    assert motion_values.speed_for_rotation_deg_s == 0.5  # 0.1 deg per 0.2 sec
    assert motion_values.shutter_time_s == 0.6
    assert motion_values.shutter_opening_deg == 0.3  # distance moved in 0.6 s

    # 1.5 * distance moved in time for accel (fudge)
    assert motion_values.acceleration_offset_deg == 0.00375
    assert motion_values.start_motion_deg == 10.00375

    assert motion_values.total_exposure_s == 360
    assert motion_values.scan_width_deg == 180
    assert motion_values.distance_to_move_deg == -180.3075


@patch(
    "dodal.common.beamlines.beamline_utils.active_device_is_same_type",
    lambda a, b: True,
)
@patch("hyperion.experiment_plans.rotation_scan_plan.rotation_scan_plan", autospec=True)
def test_rotation_scan(
    plan: MagicMock,
    RE: RunEngine,
    test_rotation_params: RotationScan,
    fake_create_rotation_devices: RotationScanComposite,
    oav_parameters_for_rotation: OAVParameters,
):
    composite = fake_create_rotation_devices
    RE(rotation_scan(composite, test_rotation_params, oav_parameters_for_rotation))

    composite.eiger.stage.assert_called()  # type: ignore
    composite.eiger.unstage.assert_called()  # type: ignore


def test_rotation_plan_runs(setup_and_run_rotation_plan_for_tests_standard) -> None:
    RE: RunEngine = setup_and_run_rotation_plan_for_tests_standard["RE_with_subs"]
    assert RE._exit_status == "success"


async def test_rotation_plan_zebra_settings(
    setup_and_run_rotation_plan_for_tests_standard,
) -> None:
    zebra: Zebra = setup_and_run_rotation_plan_for_tests_standard["zebra"]
    params: RotationScan = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]

    assert await zebra.pc.gate_start.get_value() == params.omega_start_deg
    assert await zebra.pc.pulse_start.get_value() == params.shutter_opening_time_s


async def test_full_rotation_plan_smargon_settings(
    run_full_rotation_plan,
    test_rotation_params,
) -> None:
    smargon: Smargon = run_full_rotation_plan.smargon
    params: RotationScan = test_rotation_params

    test_max_velocity = await smargon.omega.max_velocity.get_value()

    omega_set: MagicMock = get_mock_put(smargon.omega.user_setpoint)
    omega_velocity_set: MagicMock = get_mock_put(smargon.omega.velocity)
    rotation_speed = params.rotation_increment_deg / params.exposure_time_s

    assert await smargon.phi.user_readback.get_value() == params.phi_start_deg
    assert await smargon.chi.user_readback.get_value() == params.chi_start_deg
    assert await smargon.x.user_readback.get_value() == params.x_start_um / 1000  # type: ignore
    assert await smargon.y.user_readback.get_value() == params.y_start_um / 1000  # type: ignore
    assert await smargon.z.user_readback.get_value() == params.z_start_um / 1000  # type: ignore
    assert (
        # 4 * snapshots, restore omega, 1 * rotation sweep
        omega_set.call_count == 4 + 1 + 1
    )
    # 1 to max vel in outer plan, 1 to max vel in setup_oav_snapshot_plan, 1 set before rotation, 1 restore in cleanup plan
    assert omega_velocity_set.call_count == 4
    assert omega_velocity_set.call_args_list == [
        call(test_max_velocity, wait=True, timeout=10),
        call(test_max_velocity, wait=True, timeout=10),
        call(rotation_speed, wait=True, timeout=10),
        call(test_max_velocity, wait=True, timeout=10),
    ]


async def test_rotation_plan_moves_aperture_correctly(
    run_full_rotation_plan: RotationScanComposite,
    test_rotation_params,
) -> None:
    aperture_scatterguard: ApertureScatterguard = (
        run_full_rotation_plan.aperture_scatterguard
    )
    assert aperture_scatterguard.aperture_positions
    assert (
        await aperture_scatterguard._get_current_aperture_position()
        == aperture_scatterguard.aperture_positions.SMALL
    )


async def test_rotation_plan_smargon_doesnt_move_xyz_if_not_given_in_params(
    setup_and_run_rotation_plan_for_tests_nomove,
) -> None:
    smargon: Smargon = setup_and_run_rotation_plan_for_tests_nomove["smargon"]
    params: RotationScan = setup_and_run_rotation_plan_for_tests_nomove[
        "test_rotation_params"
    ]
    assert params.phi_start_deg is None
    assert params.chi_start_deg is None
    assert params.x_start_um is None
    assert params.y_start_um is None
    assert params.z_start_um is None
    for motor in [smargon.phi, smargon.chi, smargon.x, smargon.y, smargon.z]:
        assert await motor.user_readback.get_value() == 0
        get_mock_put(motor.user_setpoint).assert_not_called()  # type: ignore


@patch("hyperion.experiment_plans.rotation_scan_plan._cleanup_plan", autospec=True)
@patch("bluesky.plan_stubs.wait", autospec=True)
def test_cleanup_happens(
    bps_wait: MagicMock,
    cleanup_plan: MagicMock,
    RE: RunEngine,
    test_rotation_params,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values: RotationMotionProfile,
    oav_parameters_for_rotation: OAVParameters,
):
    class MyTestException(Exception):
        pass

    failing_set = MagicMock(
        side_effect=MyTestException("Experiment fails because this is a test")
    )

    with patch.object(fake_create_rotation_devices.smargon.omega, "set", failing_set):
        # check main subplan part fails
        with pytest.raises(MyTestException):
            RE(
                rotation_scan_plan(
                    fake_create_rotation_devices, test_rotation_params, motion_values
                )
            )
            cleanup_plan.assert_not_called()
        # check that failure is handled in composite plan
        with pytest.raises(MyTestException) as exc:
            RE(
                rotation_scan(
                    fake_create_rotation_devices,
                    test_rotation_params,
                    oav_parameters_for_rotation,
                )
            )
            assert "Experiment fails because this is a test" in exc.value.args[0]
            cleanup_plan.assert_called_once()


def test_rotation_plan_reads_hardware(
    RE: RunEngine,
    fake_create_rotation_devices: RotationScanComposite,
    test_rotation_params,
    motion_values,
    sim_run_engine_for_rotation: RunEngineSimulator,
):
    _add_sim_handlers_for_normal_operation(
        fake_create_rotation_devices, sim_run_engine_for_rotation
    )
    msgs = sim_run_engine_for_rotation.simulate_plan(
        rotation_scan_plan(
            fake_create_rotation_devices, test_rotation_params, motion_values
        )
    )

    msgs = sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "create"
        and msg.kwargs["name"] == CONST.DESCRIPTORS.HARDWARE_READ_PRE,
    )
    msgs_in_event = list(takewhile(lambda msg: msg.command != "save", msgs))
    sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs_in_event, lambda msg: msg.command == "read" and msg.obj.name == "smargon-x"
    )
    sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs_in_event, lambda msg: msg.command == "read" and msg.obj.name == "smargon-y"
    )
    sim_run_engine_for_rotation.assert_message_and_return_remaining(
        msgs_in_event, lambda msg: msg.command == "read" and msg.obj.name == "smargon-z"
    )


def test_rotation_scan_initialises_detector_distance_shutter_and_tx_fraction(
    sim_run_engine: RunEngineSimulator,
    fake_create_rotation_devices: RotationScanComposite,
    test_rotation_params: RotationScan,
    oav_parameters_for_rotation: OAVParameters,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)

    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.args[0] == 1
        and msg.obj.name == "detector_motion_shutter"
        and msg.kwargs["group"] == "setup_senv",
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.args[0] == test_rotation_params.detector_distance_mm
        and msg.obj.name == "detector_motion_z"
        and msg.kwargs["group"] == "setup_senv",
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "attenuator"
        and msg.args[0] == test_rotation_params.transmission_frac
        and msg.kwargs["group"] == "setup_senv",
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "attenuator"
        and msg.args[0] == test_rotation_params.transmission_frac
        and msg.kwargs["group"] == "setup_senv",
    )
    sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "wait" and msg.kwargs["group"] == "setup_senv"
    )


def test_rotation_scan_moves_gonio_to_start_before_snapshots(
    fake_create_rotation_devices,
    sim_run_engine,
    test_rotation_params,
    oav_parameters_for_rotation,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)
    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == CONST.WAIT.MOVE_GONIO_TO_START,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == OAV_SNAPSHOT_SETUP_GROUP,
    )


def test_rotation_scan_moves_aperture_in_backlight_out_after_snapshots_before_rotation(
    fake_create_rotation_devices,
    sim_run_engine,
    test_rotation_params,
    oav_parameters_for_rotation,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)
    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "create"
        and msg.kwargs["name"] == DocDescriptorNames.OAV_ROTATION_SNAPSHOT_TRIGGERED,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "save"
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "aperture_scatterguard"
        and msg.args[0] == AperturePositions.SMALL
        and msg.kwargs["group"] == "setup_senv",
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "backlight"
        and msg.args[0] == BacklightPosition.OUT
        and msg.kwargs["group"] == "setup_senv",
    )
    sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "wait" and msg.kwargs["group"] == "setup_senv"
    )


def test_rotation_scan_resets_omega_waits_for_sample_env_complete_after_snapshots_before_hw_read(
    fake_create_rotation_devices: RotationScanComposite,
    sim_run_engine: RunEngineSimulator,
    test_rotation_params: RotationScan,
    oav_parameters_for_rotation: OAVParameters,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)
    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "create"
        and msg.kwargs["name"] == DocDescriptorNames.OAV_ROTATION_SNAPSHOT_TRIGGERED,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "save"
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "smargon-omega"
        and msg.args[0] == test_rotation_params.omega_start_deg
        and msg.kwargs["group"] == "move_to_rotation_start",
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == "move_to_rotation_start",
    )
    sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "wait" and msg.kwargs["group"] == "setup_senv"
    )
    sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == "move_to_rotation_start",
    )
    sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "create"
        and msg.kwargs["name"] == CONST.DESCRIPTORS.ZOCALO_HW_READ,
    )


def test_rotation_snapshot_setup_called_to_move_backlight_in_aperture_out_before_triggering(
    fake_create_rotation_devices: RotationScanComposite,
    sim_run_engine: RunEngineSimulator,
    test_rotation_params: RotationScan,
    oav_parameters_for_rotation: OAVParameters,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)
    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "backlight"
        and msg.args[0] == BacklightPosition.IN
        and msg.kwargs["group"] == OAV_SNAPSHOT_SETUP_GROUP,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set"
        and msg.obj.name == "aperture_scatterguard"
        and msg.args[0] == AperturePositions.ROBOT_LOAD
        and msg.kwargs["group"] == OAV_SNAPSHOT_SETUP_GROUP,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == OAV_SNAPSHOT_SETUP_GROUP,
    )
    msgs = sim_run_engine.assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "trigger" and msg.obj.name == "oav_snapshot"
    )


def test_rotation_scan_skips_init_backlight_aperture_and_snapshots_if_snapshot_params_specified(
    fake_create_rotation_devices: RotationScanComposite,
    sim_run_engine: RunEngineSimulator,
    test_rotation_params: RotationScan,
    oav_parameters_for_rotation: OAVParameters,
):
    _add_sim_handlers_for_normal_operation(fake_create_rotation_devices, sim_run_engine)
    test_rotation_params.snapshot_omegas_deg = None

    msgs = sim_run_engine.simulate_plan(
        rotation_scan(
            fake_create_rotation_devices,
            test_rotation_params,
            oav_parameters_for_rotation,
        )
    )
    assert not [
        msg for msg in msgs if msg.kwargs.get("group", None) == OAV_SNAPSHOT_SETUP_GROUP
    ]
    assert not [
        msg for msg in msgs if msg.kwargs.get("group", None) == OAV_SNAPSHOT_GROUP
    ]
    assert (
        len(
            [
                msg
                for msg in msgs
                if msg.command == "set"
                and msg.obj.name == "smargon-omega"
                and msg.kwargs["group"] == "move_to_rotation_start"
            ]
        )
        == 1
    )


def _add_sim_handlers_for_normal_operation(
    fake_create_rotation_devices, sim_run_engine
):
    sim_run_engine.add_handler(
        "read",
        "synchrotron-synchrotron_mode",
        lambda msg: {"values": {"value": SynchrotronMode.USER}},
    )
    sim_run_engine.add_handler(
        "read",
        "synchrotron-top_up_start_countdown",
        lambda msg: {"values": {"value": -1}},
    )
    sim_run_engine.add_handler(
        "read", "smargon-omega", lambda msg: {"smargon-omega": {"value": -1}}
    )
