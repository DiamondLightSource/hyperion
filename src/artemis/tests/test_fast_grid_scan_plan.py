from src.artemis.fast_grid_scan_plan import FullParameters
from src.artemis.devices.det_dim_constants import (
    EIGER_TYPE_EIGER2_X_16M,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER2_X_4M_DIMENSION,
)


def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct():
    params = FullParameters().to_dict()
    assert params["detector"] == EIGER_TYPE_EIGER2_X_16M
    params["detector"] = EIGER_TYPE_EIGER2_X_4M
    params: FullParameters = FullParameters.from_dict(params)
    assert params.detector.det_dimension == EIGER2_X_4M_DIMENSION
