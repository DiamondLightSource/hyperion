from unittest.mock import MagicMock, patch

import pytest
from blueapi.core import BlueskyContext
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.beamlines import i03
from dodal.devices.eiger import EigerDetector
from dodal.devices.smargon import Smargon
from ophyd.sim import instantiate_fake_device

from hyperion import experiment_plans
from hyperion.experiment_plans.wait_for_robot_load_then_centre_plan import (
    WaitForRobotLoadThenCentreComposite,
    create_devices,
    wait_for_robot_load_then_centre,
)
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)


@pytest.fixture
def wait_for_robot_load_composite(
    smargon,
):
    composite = MagicMock()
    composite.smargon = smargon
    return composite


@pytest.fixture
def wait_for_robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_wait_for_robot_load_params.json"
    )
    return WaitForRobotLoadThenCentreInternalParameters(**params)


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_then_centring_plan_run_with_expected_parameters(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_composite: WaitForRobotLoadThenCentreComposite,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    RE = RunEngine()
    RE(
        wait_for_robot_load_then_centre(
            wait_for_robot_load_composite, wait_for_robot_load_then_centre_params
        )
    )
    composite_passed = mock_centring_plan.call_args[0][0]
    params_passed: PinCentreThenXrayCentreInternalParameters = (
        mock_centring_plan.call_args[0][1]
    )

    for name, value in vars(composite_passed).items():
        assert value == getattr(wait_for_robot_load_composite, name)

    assert isinstance(params_passed, PinCentreThenXrayCentreInternalParameters)


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([Msg("set_energy_plan")])),
)
def test_when_plan_run_energy_change_executes(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_composite: WaitForRobotLoadThenCentreComposite,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
    sim_run_engine,
):
    messages = sim_run_engine.simulate_plan(
        wait_for_robot_load_then_centre(
            wait_for_robot_load_composite, wait_for_robot_load_then_centre_params
        )
    )
    sim_run_engine.assert_message_and_return_remaining(
        messages, lambda msg: msg.command == "set_energy_plan"
    )


def run_simulating_smargon_wait(
    wait_for_robot_load_then_centre_params,
    wait_for_robot_load_composite,
    total_disabled_reads,
    sim_run_engine,
):
    wait_for_robot_load_composite.smargon = instantiate_fake_device(
        Smargon, name="smargon"
    )
    wait_for_robot_load_composite.eiger = instantiate_fake_device(
        EigerDetector, name="eiger"
    )

    num_of_reads = 0

    def return_not_disabled_after_reads(_):
        nonlocal num_of_reads
        num_of_reads += 1
        return {"values": {"value": int(num_of_reads < total_disabled_reads)}}

    sim_run_engine.add_handler(
        "read",
        "smargon_disabled",
        return_not_disabled_after_reads,
    )

    return sim_run_engine.simulate_plan(
        wait_for_robot_load_then_centre(
            wait_for_robot_load_composite, wait_for_robot_load_then_centre_params
        )
    )


@pytest.mark.parametrize("total_disabled_reads", [5, 3, 14])
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_given_smargon_disabled_when_plan_run_then_waits_on_smargon(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_composite: WaitForRobotLoadThenCentreComposite,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
    total_disabled_reads: int,
    sim_run_engine,
):
    messages = run_simulating_smargon_wait(
        wait_for_robot_load_then_centre_params,
        wait_for_robot_load_composite,
        total_disabled_reads,
        sim_run_engine,
    )

    mock_centring_plan.assert_called_once()

    sleep_messages = filter(lambda msg: msg.command == "sleep", messages)
    read_disabled_messages = filter(
        lambda msg: msg.command == "read" and msg.obj.name == "smargon_disabled",
        messages,
    )

    assert len(list(sleep_messages)) == total_disabled_reads - 1
    assert len(list(read_disabled_messages)) == total_disabled_reads


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_given_smargon_disabled_for_longer_than_timeout_when_plan_run_then_throws_exception(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_composite: WaitForRobotLoadThenCentreComposite,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
    sim_run_engine,
):
    with pytest.raises(TimeoutError):
        run_simulating_smargon_wait(
            wait_for_robot_load_then_centre_params,
            wait_for_robot_load_composite,
            1000,
            sim_run_engine,
        )


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_then_detector_arm_started_before_wait_on_robot_load(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_composite: WaitForRobotLoadThenCentreComposite,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
    sim_run_engine,
):
    messages = run_simulating_smargon_wait(
        wait_for_robot_load_then_centre_params,
        wait_for_robot_load_composite,
        1,
        sim_run_engine,
    )

    arm_detector_messages = filter(
        lambda msg: msg.command == "set" and msg.obj.name == "eiger_do_arm",
        messages,
    )
    read_disabled_messages = filter(
        lambda msg: msg.command == "read" and msg.obj.name == "smargon_disabled",
        messages,
    )

    arm_detector_messages = list(arm_detector_messages)
    assert len(arm_detector_messages) == 1

    idx_of_arm_message = messages.index(arm_detector_messages[0])
    idx_of_first_read_disabled_message = messages.index(list(read_disabled_messages)[0])

    assert idx_of_arm_message < idx_of_first_read_disabled_message


@pytest.mark.xfail(reason="Should we really test this")
def test_create_devices():
    context = BlueskyContext()
    context.with_plan_module(experiment_plans)

    context.with_dodal_module(
        i03,
        wait_for_connection=False,
        fake_with_ophyd_sim=True,
    )
    bluesky_context = context
    try:
        create_devices(bluesky_context)
    except Exception:
        assert False
