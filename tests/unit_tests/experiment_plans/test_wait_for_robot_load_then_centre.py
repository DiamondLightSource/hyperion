from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine

from hyperion.experiment_plans.wait_for_robot_load_then_centre import (
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
def wait_for_robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_wait_for_robot_load_params.json"
    )
    return WaitForRobotLoadThenCentreInternalParameters(**params)


@patch(
    "hyperion.experiment_plans.wait_for_robot_load_then_centre.pin_tip_centre_then_xray_centre"
)
def test_when_plan_run_then_centring_plan_run_with_expected_parameters(
    mock_centring_plan: MagicMock,
    wait_for_robot_load_then_centre_params: WaitForRobotLoadThenCentreInternalParameters,
):
    mock_composite = MagicMock()
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
