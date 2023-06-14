import os

import pytest
from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams
from nexgen.nxs_utils import Axis, Goniometer

from artemis.parameters.external_parameters import from_file
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)


@pytest.fixture
def test_rotation_params():
    param_dict = from_file(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    )
    param_dict["artemis_params"]["detector_params"][
        "directory"
    ] = "src/artemis/external_interaction/unit_tests/test_data"
    param_dict["artemis_params"]["detector_params"]["prefix"] = "TEST_FILENAME"
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.artemis_params.detector_params.exposure_time = 0.004
    params.artemis_params.detector_params.current_energy_ev = 12700
    params.artemis_params.ispyb_params.transmission = 0.49118047952
    params.artemis_params.ispyb_params.wavelength = 0.9762535433
    return params


@pytest.fixture(params=[1044])
def test_fgs_params(request):
    params = FGSInternalParameters(**default_raw_params())
    params.artemis_params.ispyb_params.wavelength = 1.0
    params.artemis_params.ispyb_params.flux = 9.0
    params.artemis_params.ispyb_params.transmission = 0.5
    params.artemis_params.detector_params.use_roi_mode = True
    params.artemis_params.detector_params.num_triggers = request.param
    params.artemis_params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.artemis_params.detector_params.prefix = "dummy"
    yield params


def create_gridscan_goniometer_axes(
    detector_params: DetectorParams, grid_scan_params: GridScanParams, grid_scan: dict
) -> Goniometer:
    """Create the data for the goniometer.

    Args:
        detector_params (DetectorParams): Information about the detector.
        grid_scan_params (GridScanParams): Information about the experiment.
        grid_scan (dict): scan midpoints from scanspec.

    Returns:
        Goniometer: A Goniometer description for nexgen
    """
    # Axis: name, depends, type, vector, start
    gonio_axes = [
        Axis("omega", ".", "rotation", (-1.0, 0.0, 0.0), detector_params.omega_start),
        Axis(
            "sam_z",
            "omega",
            "translation",
            (0.0, 0.0, 1.0),
            grid_scan_params.z_axis.start,
            grid_scan_params.z_axis.step_size,
        ),
        Axis(
            "sam_y",
            "sam_z",
            "translation",
            (0.0, 1.0, 0.0),
            grid_scan_params.y_axis.start,
            grid_scan_params.y_axis.step_size,
        ),
        Axis(
            "sam_x",
            "sam_y",
            "translation",
            (1.0, 0.0, 0.0),
            grid_scan_params.x_axis.start,
            grid_scan_params.x_axis.step_size,
        ),
        Axis("chi", "sam_x", "rotation", (0.006, -0.0264, 0.9996), 0.0),
        Axis("phi", "chi", "rotation", (-1, -0.0025, -0.0056), 0.0),
    ]
    return Goniometer(gonio_axes, grid_scan)


def create_rotation_goniometer_axes(
    detector_params: DetectorParams, scan_params: RotationScanParams
) -> Goniometer:
    """Create the data for the goniometer.

    Args:
        detector_params (DetectorParams): Information about the detector.

    Returns:
        Goniometer: A Goniometer description for nexgen
    """
    # Axis: name, depends, type, vector, start
    gonio_axes = [
        Axis(
            "omega",
            ".",
            "rotation",
            (-1.0, 0.0, 0.0),
            detector_params.omega_start,
            increment=scan_params.image_width,
            num_steps=detector_params.num_images_per_trigger,
        ),
        Axis(
            "sam_z",
            "omega",
            "translation",
            (0.0, 0.0, 1.0),
            scan_params.z,
            0.0,
        ),
        Axis(
            "sam_y",
            "sam_z",
            "translation",
            (0.0, 1.0, 0.0),
            scan_params.y,
            0.0,
        ),
        Axis(
            "sam_x",
            "sam_y",
            "translation",
            (1.0, 0.0, 0.0),
            scan_params.x,
            0.0,
        ),
        Axis("chi", "sam_x", "rotation", (0.006, -0.0264, 0.9996), 0.0),
        Axis("phi", "chi", "rotation", (-1, -0.0025, -0.0056), 0.0),
    ]
    return Goniometer(gonio_axes)
