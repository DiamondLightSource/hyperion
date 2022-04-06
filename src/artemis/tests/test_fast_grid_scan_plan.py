from src.artemis.fast_grid_scan_plan import FullParameters, get_plan
from src.artemis.devices.det_dim_constants import (
    EIGER_TYPE_EIGER2_X_16M,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER2_X_4M_DIMENSION,
)
import types


def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct():
    params = FullParameters().to_dict()
    assert params["detector_params"]["detector_size_constants"] == EIGER_TYPE_EIGER2_X_16M
    params["detector_params"]["detector_size_constants"] = EIGER_TYPE_EIGER2_X_4M
    params: FullParameters = FullParameters.from_dict(params)
    assert params.detector_params.detector_size_constants.det_dimension == EIGER2_X_4M_DIMENSION


def test_when_get_plan_called_then_generator_returned():
    plan = get_plan(FullParameters())
    assert isinstance(plan, types.GeneratorType)
