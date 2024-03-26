import json

import pytest
from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)
from pydantic import ValidationError

from hyperion.parameters.gridscan import ThreeDGridScan
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.parameters.rotation import RotationScan


@pytest.fixture
def minimal_3d_gridscan_params():
    return {
        "sample_id": 123,
        "x_start_um": 0,
        "y_start_um": 0,
        "z_start_um": 0,
        "parameter_model_version": "5.0.0",
        "visit": "cm12345",
        "file_name": "test_file_name",
        "y2_start_um": 2,
        "z2_start_um": 2,
        "x_steps": 5,
        "y_steps": 7,
        "z_steps": 9,
    }


def test_minimal_3d_gridscan_params(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    assert test_params.num_images == (5 * 7 + 5 * 9)
    assert test_params.exposure_time_s == 0.02


def test_serialise_deserialise(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    serialised = json.loads(test_params.json())
    deserialised = ThreeDGridScan(**serialised)
    assert deserialised.demand_energy_ev is None
    assert deserialised.visit == "cm12345"
    assert deserialised.x_start_um == 0.0


def test_param_version(minimal_3d_gridscan_params):
    with pytest.raises(ValidationError):
        minimal_3d_gridscan_params["parameter_model_version"] = "4.3.0"
        _ = ThreeDGridScan(**minimal_3d_gridscan_params)
    minimal_3d_gridscan_params["parameter_model_version"] = "5.0.0"
    _ = ThreeDGridScan(**minimal_3d_gridscan_params)
    minimal_3d_gridscan_params["parameter_model_version"] = "5.3.0"
    _ = ThreeDGridScan(**minimal_3d_gridscan_params)
    minimal_3d_gridscan_params["parameter_model_version"] = "5.3.7"
    _ = ThreeDGridScan(**minimal_3d_gridscan_params)
    with pytest.raises(ValidationError):
        minimal_3d_gridscan_params["parameter_model_version"] = "6.3.7"
        _ = ThreeDGridScan(**minimal_3d_gridscan_params)


def test_new_gridscan_params_equals_old():
    with open("tests/test_data/parameter_json_files/good_test_parameters.json") as f:
        old_json_data = json.loads(f.read())
    with open(
        "tests/test_data/new_parameter_json_files/good_test_parameters.json"
    ) as f:
        new_json_data = json.loads(f.read())

    old_params = GridscanInternalParameters(**old_json_data)
    new_params = ThreeDGridScan(**new_json_data)

    old_detector_params = old_params.hyperion_params.detector_params
    new_detector_params = new_params.detector_params

    assert isinstance(
        old_detector_params.beam_xy_converter, DetectorDistanceToBeamXYConverter
    )

    assert old_detector_params == new_detector_params
    assert old_params.hyperion_params.ispyb_params == new_params.ispyb_params


def test_new_rotation_params_equals_old():
    with open(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters_nomove.json"
    ) as f:
        old_json_data = json.loads(f.read())
    with open(
        "tests/test_data/new_parameter_json_files/good_test_rotation_scan_parameters_nomove.json"
    ) as f:
        new_json_data = json.loads(f.read())

    old_params = RotationInternalParameters(**old_json_data)
    new_params = RotationScan(**new_json_data)

    old_detector_params = old_params.hyperion_params.detector_params
    new_detector_params = new_params.detector_params

    assert isinstance(
        old_detector_params.beam_xy_converter, DetectorDistanceToBeamXYConverter
    )

    assert old_detector_params == new_detector_params
    assert old_params.hyperion_params.ispyb_params == new_params.ispyb_params
