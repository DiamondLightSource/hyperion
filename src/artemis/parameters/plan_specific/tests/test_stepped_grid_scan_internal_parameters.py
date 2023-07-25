import numpy as np
from dodal.devices.det_dim_constants import EIGER2_X_16M_SIZE

from artemis.parameters import external_parameters
from artemis.parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
    SteppedGridScanParams,
)


def test_stepped_grid_scan_parameters_load_from_file():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_stepped_grid_scan_parameters.json"
    )
    internal_parameters = SteppedGridScanInternalParameters(**params)

    assert isinstance(internal_parameters.experiment_params, SteppedGridScanParams)
    assert internal_parameters.experiment_params.x_steps == 5
    assert internal_parameters.experiment_params.y_steps == 10
    assert internal_parameters.experiment_params.z_steps == 2
