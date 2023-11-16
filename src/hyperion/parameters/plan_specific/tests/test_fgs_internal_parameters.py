import numpy as np
from dodal.devices.det_dim_constants import EIGER2_X_16M_SIZE
from dodal.devices.fast_grid_scan import GridScanParams


def test_FGS_parameters_load_from_file(dummy_gridscan_params):
    dummy_gridscan_params.json()

    assert isinstance(dummy_gridscan_params.experiment_params, GridScanParams)

    ispyb_params = dummy_gridscan_params.ispyb_params

    np.testing.assert_array_equal(ispyb_params.position, np.array([10, 20, 30]))
    np.testing.assert_array_equal(ispyb_params.upper_left, np.array([10, 20, 30]))

    detector_params = dummy_gridscan_params.detector_params

    assert detector_params.detector_size_constants == EIGER2_X_16M_SIZE
    assert detector_params.num_triggers == 190
    assert detector_params.num_images_per_trigger == 1
