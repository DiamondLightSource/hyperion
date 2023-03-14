from dodal.devices.det_dim_constants import EIGER2_X_16M_SIZE
from dodal.devices.fast_grid_scan import GridScanParams

from artemis.parameters.external_parameters import RawParameters
from artemis.parameters.internal_parameters import InternalParameters
from artemis.utils.utils import Point3D


def test_parameters_load_from_file():
    params = RawParameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    internal_parameters = InternalParameters(params)

    assert isinstance(internal_parameters.experiment_params, GridScanParams)

    ispyb_params = internal_parameters.artemis_params.ispyb_params

    assert ispyb_params.position == Point3D(10, 20, 30)
    assert ispyb_params.upper_left == Point3D(10, 20, 30)

    detector_params = internal_parameters.artemis_params.detector_params

    assert detector_params.detector_size_constants == EIGER2_X_16M_SIZE
