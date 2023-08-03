from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine

from artemis.experiment_plans.pin_centre_then_xray_centre_plan import (
    create_parameters_for_grid_detection,
    get_plan,
)
from artemis.parameters.external_parameters import from_file as raw_params_from_file
from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectParams,
)
from artemis.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)


@pytest.fixture
def test_pin_centre_then_xray_centre_params():
    params = raw_params_from_file(
        "src/artemis/parameters/tests/test_data/good_test_pin_centre_then_xray_centre_parameters.json"
    )
    return PinCentreThenXrayCentreInternalParameters(**params)


def test_when_create_parameters_for_grid_detection_thne_parameters_created(
    test_pin_centre_then_xray_centre_params: PinCentreThenXrayCentreInternalParameters,
):
    grid_detect_params = create_parameters_for_grid_detection(
        test_pin_centre_then_xray_centre_params
    )

    assert isinstance(
        grid_detect_params.experiment_params, GridScanWithEdgeDetectParams
    )
    assert grid_detect_params.experiment_params.exposure_time == 0.1


@patch(
    "artemis.experiment_plans.pin_centre_then_xray_centre_plan.pin_tip_centre_plan",
    autospec=True,
)
@patch(
    "artemis.experiment_plans.pin_centre_then_xray_centre_plan.detect_grid_and_do_gridscan",
    autospec=True,
)
def test_when_pin_centre_xray_centre_get_plan_called_then_plan_runs_correctly(
    mock_detect_and_do_gridscan: MagicMock,
    mock_pin_tip_centre: MagicMock,
    test_pin_centre_then_xray_centre_params: PinCentreThenXrayCentreInternalParameters,
):
    RE = RunEngine()
    RE(get_plan(test_pin_centre_then_xray_centre_params))

    mock_detect_and_do_gridscan.assert_called_once()
    mock_pin_tip_centre.assert_called_once()
