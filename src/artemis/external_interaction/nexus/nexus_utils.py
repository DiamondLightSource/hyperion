"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams
from nexgen.nxs_utils import Attenuator, Axis, Beam, Detector, EigerDetector, Goniometer

from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)


def get_current_time():
    return datetime.utcfromtimestamp(time.time()).strftime(r"%Y-%m-%dT%H:%M:%SZ")


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
            0,
        ),
        Axis(
            "sam_y",
            "sam_z",
            "translation",
            (0.0, 1.0, 0.0),
            scan_params.y,
            0,
        ),
        Axis(
            "sam_x",
            "sam_y",
            "translation",
            (1.0, 0.0, 0.0),
            scan_params.x,
            0,
        ),
        Axis("chi", "sam_x", "rotation", (0.006, -0.0264, 0.9996), 0.0),
        Axis("phi", "chi", "rotation", (-1, -0.0025, -0.0056), 0.0),
    ]
    return Goniometer(gonio_axes)


def create_detector_parameters(detector_params: DetectorParams) -> Detector:
    """Returns the detector information in a format that nexgen wants.

    Args:
        detector_params (DetectorParams): The detector params as Artemis stores them.

    Returns:
        Detector: Detector description for nexgen.
    """
    detector_pixels = detector_params.get_detector_size_pizels()

    eiger_params = EigerDetector(
        "Eiger 16M", (detector_pixels.height, detector_pixels.width), "Si", 46051, 0
    )

    detector_axes = [
        Axis(
            "det_z",
            ".",
            "translation",
            (0.0, 0.0, 1.0),
            detector_params.detector_distance,
        )
    ]
    # Eiger parameters, axes, beam_center, exp_time, [fast, slow]
    return Detector(
        eiger_params,
        detector_axes,
        detector_params.get_beam_position_pixels(detector_params.detector_distance),
        detector_params.exposure_time,
        [(-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)],
    )


def create_beam_and_attenuator_parameters(
    ispyb_params: IspybParams,
) -> tuple[Beam, Attenuator]:
    """Create beam and attenuator dictionaries that nexgen can understand.

    Args:
        ispyb_params (IspybParams): An IspybParams object holding all required data.

    Returns:
        tuple[Beam, Attenuator]: Descriptions of the beam and attenuator for nexgen.
    """
    return (
        Beam(ispyb_params.wavelength, ispyb_params.flux),
        Attenuator(ispyb_params.transmission),
    )
