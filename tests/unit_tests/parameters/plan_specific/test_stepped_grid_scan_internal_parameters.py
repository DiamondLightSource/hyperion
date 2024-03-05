import unit_tests.conftest
from hyperion.parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
    SteppedGridScanParams,
)


def test_stepped_grid_scan_parameters_load_from_file():
    params = unit_tests.conftest.from_file(
        "tests/test_data/parameter_json_files/good_test_stepped_grid_scan_parameters.json"
    )
    internal_parameters = SteppedGridScanInternalParameters(**params)

    assert isinstance(internal_parameters.experiment_params, SteppedGridScanParams)
    assert internal_parameters.experiment_params.x_steps == 5
    assert internal_parameters.experiment_params.y_steps == 10
    assert internal_parameters.experiment_params.z_steps == 2
