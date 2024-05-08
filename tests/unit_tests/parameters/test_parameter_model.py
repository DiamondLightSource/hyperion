import json

import pytest
from pydantic import ValidationError

from hyperion.parameters.gridscan import (
    RobotLoadThenCentre,
    ThreeDGridScan,
)


@pytest.fixture
def minimal_3d_gridscan_params():
    return {
        "sample_id": 123,
        "x_start_um": 0.123,
        "y_start_um": 0.777,
        "z_start_um": 0.05,
        "parameter_model_version": "5.0.0",
        "visit": "cm12345",
        "file_name": "test_file_name",
        "y2_start_um": 2,
        "z2_start_um": 2,
        "x_steps": 5,
        "y_steps": 7,
        "z_steps": 9,
        "storage_directory": "/tmp/dls/i03/data/2024/cm31105-4/xraycentring/123456/",
        "ispyb_extras": {
            "position": [0, 0, 0],
            "beam_size_x": 0,
            "beam_size_y": 0,
            "focal_spot_size_x": 0,
            "focal_spot_size_y": 0,
        },
    }


def test_minimal_3d_gridscan_params(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    assert {"sam_x", "sam_y", "sam_z", "omega"} == set(test_params.scan_points.keys())
    assert test_params.scan_indices == [0, 35]
    assert test_params.num_images == (5 * 7 + 5 * 9)
    assert test_params.exposure_time_s == 0.02


def test_serialise_deserialise(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    serialised = json.loads(test_params.json())
    deserialised = ThreeDGridScan(**serialised)
    assert deserialised.demand_energy_ev is None
    assert deserialised.visit == "cm12345"
    assert deserialised.x_start_um == 0.123


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


def test_robot_load_then_centre_params():
    params = {
        "parameter_model_version": "5.0.0",
        "sample_id": 123456,
        "visit": "cm12345",
        "file_name": "file_name",
        "storage_directory": "/tmp/dls/i03/data/2024/cm31105-4/xraycentring/123456/",
        "ispyb_extras": {
            "beam_size_x": 0.05,
            "beam_size_y": 0.05,
            "focal_spot_size_x": 0.06,
            "focal_spot_size_y": 0.06,
            "position": [0, 0, 0],
        },
    }
    params["detector_distance_mm"] = 200
    test_params = RobotLoadThenCentre(**params)
    assert test_params.visit_directory
    assert test_params.detector_params
