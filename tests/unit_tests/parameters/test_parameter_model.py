import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hyperion.parameters.gridscan import (
    OddYStepsException,
    RobotLoadThenCentre,
    ThreeDGridScan,
)
from hyperion.parameters.rotation import RotationScan

from ...conftest import raw_params_from_file


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
    }


def test_minimal_3d_gridscan_params(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    assert {"sam_x", "sam_y", "sam_z"} == set(test_params.scan_points.keys())
    assert test_params.scan_indices == [0, 35]
    assert test_params.num_images == (5 * 7 + 5 * 9)
    assert test_params.exposure_time_s == 0.02


def test_cant_do_panda_fgs_with_odd_y_steps(minimal_3d_gridscan_params):
    test_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    with pytest.raises(OddYStepsException):
        test_params.panda_FGS_params
    assert test_params.FGS_params


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
    }
    params["detector_distance_mm"] = 200
    test_params = RobotLoadThenCentre(**params)
    assert test_params.visit_directory
    assert test_params.detector_params


def test_default_snapshot_path(minimal_3d_gridscan_params):
    gridscan_params = ThreeDGridScan(**minimal_3d_gridscan_params)
    assert gridscan_params.snapshot_directory == Path(
        "/tmp/dls/i03/data/2024/cm31105-4/xraycentring/123456/snapshots"
    )

    params_with_snapshot_path = dict(minimal_3d_gridscan_params)
    params_with_snapshot_path["snapshot_directory"] = "/tmp/my_snapshots"

    gridscan_params_with_snapshot_path = ThreeDGridScan(**params_with_snapshot_path)
    assert gridscan_params_with_snapshot_path.snapshot_directory == Path(
        "/tmp/my_snapshots"
    )


def test_osc_is_used():
    raw_params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    for osc in [0.001, 0.05, 0.1, 0.2, 0.75, 1, 1.43]:
        raw_params["rotation_increment_deg"] = osc
        params = RotationScan(**raw_params)
        assert params.rotation_increment_deg == osc
        assert params.num_images == int(params.scan_width_deg / osc)
