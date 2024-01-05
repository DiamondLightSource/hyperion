from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.eiger import EigerDetector
from dodal.devices.smargon import Smargon
from ophyd.sim import instantiate_fake_device

from hyperion.experiment_plans.wait_for_robot_load_then_centre_plan import (
    wait_for_robot_load_then_centre,
)
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)

from .conftest import RunEngineSimulator


@pytest.fixture
def wait_for_robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_wait_for_robot_load_params.json"
    )
    return WaitForRobotLoadThenCentreInternalParameters(**params)


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
def test_when_plan_run_then_centring_plan_run_with_expected_parameters(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    mock_composite = MagicMock()
    mock_composite.smargon = instantiate_fake_device(Smargon, name="smargon")

    RE = RunEngine()
    RE(
        wait_for_robot_load_then_centre(
            mock_composite, wait_for_robot_load_then_centre_params
        )
    )
    composite_passed = mock_centring_plan.call_args[0][0]
    params_passed: PinCentreThenXrayCentreInternalParameters = (
        mock_centring_plan.call_args[0][1]
    )

    assert composite_passed == mock_composite
    assert isinstance(params_passed, PinCentreThenXrayCentreInternalParameters)


def run_simulating_smargon_wait(
    wait_for_robot_load_then_centre_params, total_disabled_reads
):
    mock_composite = MagicMock()
    mock_composite.smargon = instantiate_fake_device(Smargon, name="smargon")
    mock_composite.eiger = instantiate_fake_device(EigerDetector, name="eiger")

    num_of_reads = 0

    def return_not_disabled_after_reads(_):
        nonlocal num_of_reads
        num_of_reads += 1
        return {"values": {"value": int(num_of_reads < total_disabled_reads)}}

    sim = RunEngineSimulator()
    sim.add_handler(
        "read",
        "smargon_disabled",
        return_not_disabled_after_reads,
    )

    return sim.simulate_plan(
        wait_for_robot_load_then_centre(
            mock_composite, wait_for_robot_load_then_centre_params
        )
    )


@pytest.mark.parametrize("total_disabled_reads", [5, 3, 14])
@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
def test_given_smargon_disabled_when_plan_run_then_waits_on_smargon(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
    total_disabled_reads: int,
):
    messages = run_simulating_smargon_wait(
        wait_for_robot_load_then_centre_params, total_disabled_reads
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
def test_given_smargon_disabled_for_longer_than_timeout_when_plan_run_then_throws_exception(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    with pytest.raises(TimeoutError):
        run_simulating_smargon_wait(wait_for_robot_load_then_centre_params, 1000)


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
def test_when_plan_run_then_detector_arm_started_before_wait_on_robot_load(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    messages = run_simulating_smargon_wait(wait_for_robot_load_then_centre_params, 1)

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
