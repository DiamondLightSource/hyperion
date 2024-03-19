from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Callable
from unittest.mock import DEFAULT, MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.smargon import Smargon
from dodal.devices.zebra import Zebra
from ophyd.status import Status

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationMotionProfile,
    RotationScanComposite,
    calculate_motion_profile,
    rotation_scan,
    rotation_scan_plan,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

from .conftest import fake_read

if TYPE_CHECKING:
    from dodal.devices.smargon import Smargon


TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def do_rotation_main_plan_for_tests(
    run_eng: RunEngine,
    expt_params: RotationInternalParameters,
    devices: RotationScanComposite,
    motion_values: RotationMotionProfile,
    plan: Callable = rotation_scan_plan,
):
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        run_eng(
            plan(devices, expt_params, motion_values),
        )


@pytest.fixture
def run_full_rotation_plan(
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
):
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        RE(
            rotation_scan(fake_create_rotation_devices, test_rotation_params),
        )
        return fake_create_rotation_devices


@pytest.fixture
def motion_values(test_rotation_params: RotationInternalParameters):
    return calculate_motion_profile(
        test_rotation_params.hyperion_params.detector_params,
        test_rotation_params.experiment_params,
        0.005,
        222,
    )


def setup_and_run_rotation_plan_for_tests(
    RE: RunEngine,
    test_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    smargon = fake_create_rotation_devices.smargon

    def side_set_w_return(obj, *args):
        obj.sim_put(*args)
        return DEFAULT

    smargon.omega.velocity.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.omega.velocity),
    )

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
    test_rotation_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    return setup_and_run_rotation_plan_for_tests(
        RE, test_rotation_params, fake_create_rotation_devices, motion_values
    )


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_nomove(
    RE: RunEngine,
    test_rotation_params_nomove: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values,
):
    return setup_and_run_rotation_plan_for_tests(
        RE, test_rotation_params_nomove, fake_create_rotation_devices, motion_values
    )


def test_rotation_scan_calculations(test_rotation_params: RotationInternalParameters):
    test_rotation_params.hyperion_params.detector_params.exposure_time = 0.2
    test_rotation_params.hyperion_params.detector_params.omega_start = 10
    test_rotation_params.experiment_params.omega_start = 10

    motion_values = calculate_motion_profile(
        test_rotation_params.hyperion_params.detector_params,
        test_rotation_params.experiment_params,
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


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("hyperion.experiment_plans.rotation_scan_plan.rotation_scan_plan", autospec=True)
def test_rotation_scan(
    plan: MagicMock,
    RE: RunEngine,
    test_rotation_params,
    fake_create_rotation_devices: RotationScanComposite,
):
    composite = fake_create_rotation_devices
    RE(rotation_scan(composite, test_rotation_params))

    composite.eiger.stage.assert_called()  # type: ignore
    composite.eiger.unstage.assert_called()  # type: ignore


def test_rotation_plan_runs(setup_and_run_rotation_plan_for_tests_standard) -> None:
    RE: RunEngine = setup_and_run_rotation_plan_for_tests_standard["RE_with_subs"]
    assert RE._exit_status == "success"


async def test_rotation_plan_zebra_settings(
    setup_and_run_rotation_plan_for_tests_standard,
) -> None:
    zebra: Zebra = setup_and_run_rotation_plan_for_tests_standard["zebra"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert await zebra.pc.gate_start.get_value() == expt_params.omega_start
    assert await zebra.pc.gate_start.get_value() == expt_params.omega_start
    assert await zebra.pc.pulse_start.get_value() == expt_params.shutter_opening_time_s


def test_rotation_plan_energy_settings(setup_and_run_rotation_plan_for_tests_standard):
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]

    assert (
        params.hyperion_params.detector_params.expected_energy_ev == 100
    )  # from good_test_rotation_scan_parameters.json
    assert (
        params.hyperion_params.detector_params.expected_energy_ev
        == params.hyperion_params.ispyb_params.current_energy_ev
    )


def test_full_rotation_plan_smargon_settings(
    run_full_rotation_plan,
    test_rotation_params,
) -> None:
    smargon: Smargon = run_full_rotation_plan.smargon
    params: RotationInternalParameters = test_rotation_params
    expt_params = params.experiment_params

    test_max_velocity = smargon.omega.max_velocity.get()

    omega_set: MagicMock = smargon.omega.set  # type: ignore
    omega_velocity_set: MagicMock = smargon.omega.velocity.set  # type: ignore
    rotation_speed = (
        expt_params.image_width / params.hyperion_params.detector_params.exposure_time
    )

    assert smargon.phi.user_readback.get() == expt_params.phi_start
    assert smargon.chi.user_readback.get() == expt_params.chi_start
    assert smargon.x.user_readback.get() == expt_params.x
    assert smargon.y.user_readback.get() == expt_params.y
    assert smargon.z.user_readback.get() == expt_params.z
    assert omega_set.call_count == 2
    assert omega_velocity_set.call_count == 3
    assert omega_velocity_set.call_args_list == [
        call(test_max_velocity),
        call(rotation_speed),
        call(test_max_velocity),
    ]


def test_rotation_plan_smargon_doesnt_move_xyz_if_not_given_in_params(
    setup_and_run_rotation_plan_for_tests_nomove,
) -> None:
    smargon: Smargon = setup_and_run_rotation_plan_for_tests_nomove["smargon"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_nomove[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert expt_params.phi_start is None
    assert expt_params.chi_start is None
    assert expt_params.x is None
    assert expt_params.y is None
    assert expt_params.z is None
    for motor in [smargon.phi, smargon.chi, smargon.x, smargon.y, smargon.z]:
        assert motor.user_readback.get() == 0
        motor.set.assert_not_called()  # type: ignore


@patch("hyperion.experiment_plans.rotation_scan_plan.cleanup_plan", autospec=True)
@patch("bluesky.plan_stubs.wait", autospec=True)
def test_cleanup_happens(
    bps_wait: MagicMock,
    cleanup_plan: MagicMock,
    RE: RunEngine,
    test_rotation_params,
    fake_create_rotation_devices: RotationScanComposite,
    motion_values: RotationMotionProfile,
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
            RE(rotation_scan(fake_create_rotation_devices, test_rotation_params))
            assert "Experiment fails because this is a test" in exc.value.args[0]
            cleanup_plan.assert_called_once()
