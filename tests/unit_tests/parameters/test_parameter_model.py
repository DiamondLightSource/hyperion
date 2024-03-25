import json

from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)

from hyperion.parameters.gridscan import ThreeDGridScan
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def test_minimal_3d_gridscan_params():
    test_params = ThreeDGridScan(
        sample_id=123,
        x_start_um=0,
        y_start_um=0,
        z_start_um=0,
        parameter_model_version="5.0.0",  # type: ignore
        visit="cm12345",
        file_name="test_file_name",
        y2_start_um=2,
        z2_start_um=2,
        x_steps=5,
        y_steps=7,
        z_steps=9,
    )
    assert test_params.num_images == (5 * 7 + 5 * 9)
    assert test_params.exposure_time_s == 0.02


def test_new_params_equals_old():
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
