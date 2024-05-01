import json

import pytest
from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)
from pydantic import ValidationError

from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import (
    PinTipCentreThenXrayCentre,
    RobotLoadThenCentre,
    ThreeDGridScan,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.parameters.rotation import RotationScan


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


def test_new_gridscan_params_equals_old():
    # Can be removed in #1277
    with open("tests/test_data/parameter_json_files/good_test_parameters.json") as f:
        old_json_data = json.loads(f.read())
    with open(
        "tests/test_data/new_parameter_json_files/good_test_parameters.json"
    ) as f:
        new_json_data = json.loads(f.read())

    new_json_data["x_steps"] = 10
    new_json_data["y_steps"] = 5
    new_json_data["z_steps"] = 1
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
    # Can be removed in #1277
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


class TestNewGdaParams:
    # Can be removed in #1277

    energy = 12123
    filename = "samplefilenametest"
    omega_start = 0.023
    transmission = 45 / 100
    visit = "cm66666-6"
    microns_per_pixel_x = 0.7844
    microns_per_pixel_y = 0.7111
    position = [123.0, 234.0, 345.0]
    beam_size_x = 131 / 1000.0
    beam_size_y = 204 / 1000.0
    focal_spot_size_x = 468
    focal_spot_size_y = 787
    sample_id = 456789
    exposure_time_s = 0.004
    detector_distance_mm = 242
    chi = 27.0
    rotation_inc = 0.56
    rotation_axis = "omega"
    rotation_direction = "Negative"
    rotation_comment = "Hyperion rotation scan - "
    directory = "/tmp/dls/i03/data/2024/cm66666-6/xraycentring/456789/"

    def test_pin_then_xray(self):
        new_hyperion_params_dict = {
            "parameter_model_version": "5.0.0",
            "demand_energy_ev": self.energy,
            "exposure_time_s": self.exposure_time_s,
            "detector_distance_mm": self.detector_distance_mm,
            "visit": self.visit,
            "omega_start_deg": self.omega_start,
            "file_name": self.filename,
            "sample_id": self.sample_id,
            "use_roi_mode": False,
            "transmission_frac": self.transmission,
            "zocalo_environment": "artemis",
            "storage_directory": self.directory,
            "ispyb_extras": {
                "position": self.position,
                "beam_size_x": self.beam_size_x,
                "beam_size_y": self.beam_size_y,
                "focal_spot_size_x": self.focal_spot_size_x,
                "focal_spot_size_y": self.focal_spot_size_y,
            },
        }
        old_hyperion_params_dict = {
            "params_version": "5.0.0",
            "hyperion_params": {
                "beamline": CONST.I03.BEAMLINE,
                "insertion_prefix": CONST.I03.INSERTION_PREFIX,
                "zocalo_environment": "artemis",
                "experiment_type": "pin_centre_then_xray_centre",
                "detector_params": {
                    "expected_energy_ev": self.energy,
                    "directory": self.directory,
                    "prefix": self.filename,
                    "use_roi_mode": False,
                    "detector_size_constants": CONST.I03.DETECTOR,
                    "run_number": 1,
                    "det_dist_to_beam_converter_path": CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH,
                },
                "ispyb_params": {
                    "current_energy_ev": self.energy,
                    "sample_id": self.sample_id,
                    "visit_path": "/tmp/dls/i03/data/2024/cm66666-6",
                    "undulator_gap": 0.5,
                    "microns_per_pixel_x": self.microns_per_pixel_x,
                    "microns_per_pixel_y": self.microns_per_pixel_y,
                    "position": self.position,
                    "beam_size_x": self.beam_size_x,
                    "beam_size_y": self.beam_size_y,
                    "focal_spot_size_x": self.focal_spot_size_x,
                    "focal_spot_size_y": self.focal_spot_size_y,
                    "resolution": 1.57,
                    "comment": "",
                },
            },
            "experiment_params": {
                "transmission_fraction": self.transmission,
                "snapshot_dir": "/tmp/dls/i03/data/2024/cm66666-6/snapshots",
                "detector_distance": self.detector_distance_mm,
                "exposure_time": self.exposure_time_s,
                "omega_start": self.omega_start,
                "grid_width_microns": 600,
                "tip_offset_microns": 0,
                "set_stub_offsets": False,
            },
        }
        new_params = PinTipCentreThenXrayCentre(**new_hyperion_params_dict)
        old_params = PinCentreThenXrayCentreInternalParameters(
            **old_hyperion_params_dict
        )

        new_old_params = new_params.old_parameters()

        # This should all be stuff that is no longer needed because
        # we get it from devices!
        old_params.hyperion_params.ispyb_params.resolution = None
        old_params.hyperion_params.ispyb_params.undulator_gap = None
        old_params.hyperion_params.ispyb_params.xtal_snapshots_omega_end = []
        old_params.hyperion_params.ispyb_params.xtal_snapshots_omega_start = []

        assert new_old_params == old_params

    def test_rotation_new_params(self):
        new_hyperion_params_dict = {
            "parameter_model_version": "5.0.0",
            "comment": self.rotation_comment,
            "detector_distance_mm": self.detector_distance_mm,
            "demand_energy_ev": self.energy,
            "exposure_time_s": self.exposure_time_s,
            "omega_start_deg": self.omega_start,
            "chi_start_deg": self.chi,
            "file_name": self.filename,
            "scan_width_deg": self.rotation_inc * 1001,
            "rotation_axis": self.rotation_axis,
            "storage_directory": self.directory,
            "rotation_direction": self.rotation_direction,
            "rotation_increment_deg": self.rotation_inc,
            "sample_id": self.sample_id,
            "visit": self.visit,
            "zocalo_environment": "artemis",
            "transmission_frac": self.transmission,
            "ispyb_extras": {
                "xtal_snapshots_omega_start": ["test1", "test2", "test3"],
                "xtal_snapshots_omega_end": ["", "", ""],
                "position": self.position,
                "beam_size_x": self.beam_size_x,
                "beam_size_y": self.beam_size_y,
                "focal_spot_size_x": self.focal_spot_size_x,
                "focal_spot_size_y": self.focal_spot_size_y,
            },
        }

        old_hyperion_params_dict = {
            "params_version": "5.0.0",
            "hyperion_params": {
                "beamline": CONST.I03.BEAMLINE,
                "insertion_prefix": CONST.I03.INSERTION_PREFIX,
                "detector": "EIGER2_X_16M",
                "zocalo_environment": "artemis",
                "experiment_type": "SAD",
                "detector_params": {
                    "expected_energy_ev": self.energy,
                    "directory": self.directory,
                    "prefix": self.filename,
                    "use_roi_mode": False,
                    "detector_size_constants": CONST.I03.DETECTOR,
                    "run_number": 1,
                    "det_dist_to_beam_converter_path": CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH,
                },
                "ispyb_params": {
                    "ispyb_experiment_type": "SAD",
                    "current_energy_ev": self.energy,
                    "sample_id": self.sample_id,
                    "visit_path": "/tmp/dls/i03/data/2024/cm66666-6",
                    "undulator_gap": 0.5,
                    "microns_per_pixel_x": self.microns_per_pixel_x,
                    "microns_per_pixel_y": self.microns_per_pixel_y,
                    "position": self.position,
                    "beam_size_x": self.beam_size_x,
                    "beam_size_y": self.beam_size_y,
                    "focal_spot_size_x": self.focal_spot_size_x,
                    "focal_spot_size_y": self.focal_spot_size_y,
                    "resolution": 1.57,
                    "comment": self.rotation_comment,
                    "xtal_snapshots_omega_start": ["test1", "test2", "test3"],
                    "xtal_snapshots_omega_end": ["", "", ""],
                    "xtal_snapshots": ["", "", ""],
                },
            },
            "experiment_params": {
                "transmission_fraction": self.transmission,
                "rotation_axis": self.rotation_axis,
                "chi_start": self.chi,
                "rotation_angle": self.rotation_inc * 1001,
                "omega_start": self.omega_start,
                "exposure_time": self.exposure_time_s,
                "detector_distance": self.detector_distance_mm,
                "rotation_increment": self.rotation_inc,
                "image_width": self.rotation_inc,
                "positive_rotation_direction": False,
                "shutter_opening_time_s": 0.06,
            },
        }

        new_params = RotationScan(**new_hyperion_params_dict)
        old_params = RotationInternalParameters(**old_hyperion_params_dict)

        new_old_params = new_params.old_parameters()

        # This should all be stuff that is no longer needed because
        # we get it from devices!
        old_params.hyperion_params.ispyb_params.resolution = None
        old_params.hyperion_params.ispyb_params.undulator_gap = None

        assert new_old_params == old_params
