from dodal.devices.det_dim_constants import EIGER2_X_16M_SIZE

from artemis.parameters import external_parameters
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)
from artemis.utils import Point3D


def test_rotation_parameters_load_from_file():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    )
    internal_parameters = RotationInternalParameters(params)

    assert isinstance(internal_parameters.experiment_params, RotationScanParams)

    ispyb_params = internal_parameters.artemis_params.ispyb_params

    assert ispyb_params.position == Point3D(10, 20, 30)
    assert ispyb_params.upper_left == Point3D(10, 20, 30)

    detector_params = internal_parameters.artemis_params.detector_params

    assert detector_params.detector_size_constants == EIGER2_X_16M_SIZE
