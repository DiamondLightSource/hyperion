from hyperion.parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
    SteppedGridScanParams,
)


def test_stepped_grid_scan_parameters_load_from_file(dummy_external_gridscan_params):
    internal_parameters = SteppedGridScanInternalParameters.from_external(
        dummy_external_gridscan_params
    )

    assert isinstance(internal_parameters.experiment_params, SteppedGridScanParams)
    assert internal_parameters.experiment_params.x_steps == 5
    assert internal_parameters.experiment_params.y_steps == 10
    assert internal_parameters.experiment_params.z_steps == 2
