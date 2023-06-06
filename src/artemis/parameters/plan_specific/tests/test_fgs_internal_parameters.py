import numpy as np
from dodal.devices.det_dim_constants import EIGER2_X_16M_SIZE
from dodal.devices.fast_grid_scan import GridScanParams

from artemis.parameters import external_parameters
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


def test_FGS_parameters_load_from_file():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    internal_parameters = FGSInternalParameters(**params)

    assert isinstance(internal_parameters.experiment_params, GridScanParams)

    ispyb_params = internal_parameters.artemis_params.ispyb_params

    np.testing.assert_array_equal(ispyb_params.position, np.array([10, 20, 30]))
    np.testing.assert_array_equal(ispyb_params.upper_left, np.array([10, 20, 30]))

    detector_params = internal_parameters.artemis_params.detector_params

    assert detector_params.detector_size_constants == EIGER2_X_16M_SIZE
    assert detector_params.num_triggers == 60
    assert detector_params.num_images_per_trigger == 1
