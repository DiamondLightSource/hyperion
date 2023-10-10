from __future__ import annotations

import time
from datetime import datetime, timedelta

from dodal.devices.detector import DetectorParams
from nexgen.nxs_utils import Attenuator, Axis, Beam, Detector, EigerDetector, Goniometer
from nexgen.nxs_utils.Axes import TransformationType

from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams


def create_goniometer_axes(
    omega_start: float,
    scan_points: dict | None,
    x_y_z_increments: tuple[float, float, float] = (0.0, 0.0, 0.0),
):
    """Returns a Nexgen 'Goniometer' object with the dependency chain of I03's Smargon
    goniometer. If scan points is provided these values will be used in preference to
    those from the params object.

    Args:
        omega_start (float): the starting position of omega, the only extra value that
                             needs to be specified except for the scan points.
        scan_points (dict):  a dictionary of points in the scan for each axis. Obtained
                             by calculating the scan path with scanspec and calling
                             consume() on it.
        x_y_z_increments:    optionally, specify the increments between each image for
                             the x, y, and z axes. Will be ignored if scan_points
                             is provided.
    """
    gonio_axes = [
        Axis("omega", ".", TransformationType.ROTATION, (-1.0, 0.0, 0.0), omega_start),
        Axis(
            name="sam_z",
            depends="omega",
            transformation_type=TransformationType.TRANSLATION,
            vector=(0.0, 0.0, 1.0),
            start_pos=0.0,
            increment=x_y_z_increments[2],
        ),
        Axis(
            name="sam_y",
            depends="sam_z",
            transformation_type=TransformationType.TRANSLATION,
            vector=(0.0, 1.0, 0.0),
            start_pos=0.0,
            increment=x_y_z_increments[1],
        ),
        Axis(
            name="sam_x",
            depends="sam_y",
            transformation_type=TransformationType.TRANSLATION,
            vector=(1.0, 0.0, 0.0),
            start_pos=0.0,
            increment=x_y_z_increments[0],
        ),
        Axis(
            "chi", "sam_x", TransformationType.ROTATION, (0.006, -0.0264, 0.9996), 0.0
        ),
        Axis("phi", "chi", TransformationType.ROTATION, (-1, -0.0025, -0.0056), 0.0),
    ]
    return Goniometer(gonio_axes, scan_points)


def get_start_and_predicted_end_time(time_expected: float) -> tuple[str, str]:
    start = datetime.utcfromtimestamp(time.time())
    end_est = start + timedelta(seconds=time_expected)
    return start.strftime(r"%Y-%m-%dT%H:%M:%SZ"), end_est.strftime(
        r"%Y-%m-%dT%H:%M:%SZ"
    )


def create_detector_parameters(detector_params: DetectorParams) -> Detector:
    """Returns the detector information in a format that nexgen wants.

    Args:
        detector_params (DetectorParams): The detector params as Hyperion stores them.

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
            TransformationType.TRANSLATION,
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
        Attenuator(ispyb_params.transmission_fraction),
    )
