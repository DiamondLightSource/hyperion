from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import DEFAULT, MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.smargon import Smargon
from dodal.devices.zebra import Zebra
from ophyd.status import Status

from hyperion.experiment_plans.rotation_scan_plan import (
    DEFAULT_MAX_VELOCITY,
    RotationScanComposite,
    rotation_scan,
    rotation_scan_plan,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
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
    run_eng_w_subs: tuple[RunEngine, RotationCallbackCollection],
    expt_params: RotationInternalParameters,
    devices: RotationScanComposite,
    plan=rotation_scan_plan,
):
    run_engine, _ = run_eng_w_subs
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        run_engine(
            plan(
                devices,
                expt_params,
            ),
        )


@pytest.fixture
def RE_with_subs(
    RE: RunEngine, mock_rotation_subscriptions: RotationCallbackCollection
):
    for cb in mock_rotation_subscriptions:
        RE.subscribe(cb)
    return RE, mock_rotation_subscriptions


@pytest.fixture
def run_full_rotation_plan(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
):
    do_rotation_main_plan_for_tests(
        RE_with_subs, test_rotation_params, fake_create_rotation_devices, rotation_scan
    )
    return fake_create_rotation_devices


def setup_and_run_rotation_plan_for_tests(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
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
            RE_with_subs,
            test_params,
            fake_create_rotation_devices,
        )

    return {
        "RE_with_subs": RE_with_subs,
        "test_rotation_params": test_params,
        "smargon": fake_create_rotation_devices.smargon,
        "zebra": fake_create_rotation_devices.zebra,
    }


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_standard(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
):
    return setup_and_run_rotation_plan_for_tests(
        RE_with_subs,
        test_rotation_params,
        fake_create_rotation_devices,
    )


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_nomove(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params_nomove: RotationInternalParameters,
    fake_create_rotation_devices: RotationScanComposite,
):
    return setup_and_run_rotation_plan_for_tests(
        RE_with_subs,
        test_rotation_params_nomove,
        fake_create_rotation_devices,
    )


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("hyperion.experiment_plans.rotation_scan_plan.rotation_scan_plan", autospec=True)
def test_rotation_scan(
    plan: MagicMock,
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params,
    fake_create_rotation_devices: RotationScanComposite,
):
    RE, _ = RE_with_subs

    composite = fake_create_rotation_devices
    RE(rotation_scan(composite, test_rotation_params))

    composite.eiger.stage.assert_called()  # type: ignore
    composite.eiger.unstage.assert_called()  # type: ignore


def test_rotation_plan_runs(setup_and_run_rotation_plan_for_tests_standard) -> None:
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection] = (
        setup_and_run_rotation_plan_for_tests_standard["RE_with_subs"]
    )
    RE, _ = RE_with_subs
    assert RE._exit_status == "success"


def test_rotation_plan_zebra_settings(
    setup_and_run_rotation_plan_for_tests_standard,
) -> None:
    zebra: Zebra = setup_and_run_rotation_plan_for_tests_standard["zebra"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.pulse_start.get() == expt_params.shutter_opening_time_s


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
        call(DEFAULT_MAX_VELOCITY),
        call(rotation_speed),
        call(DEFAULT_MAX_VELOCITY),
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
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params,
    fake_create_rotation_devices: RotationScanComposite,
):
    RE, _ = RE_with_subs

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
                    fake_create_rotation_devices,
                    test_rotation_params,
                )
            )
            cleanup_plan.assert_not_called()
        # check that failure is handled in composite plan
        with pytest.raises(MyTestException) as exc:
            RE(
                rotation_scan(
                    fake_create_rotation_devices,
                    test_rotation_params,
                )
            )
            assert "Experiment fails because this is a test" in exc.value.args[0]
            cleanup_plan.assert_called_once()
