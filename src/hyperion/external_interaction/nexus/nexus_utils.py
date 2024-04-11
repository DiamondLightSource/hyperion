from __future__ import annotations

import time
from datetime import datetime, timedelta

import numpy as np
from dodal.devices.detector import DetectorParams
from nexgen.nxs_utils import Attenuator, Axis, Beam, Detector, EigerDetector, Goniometer
from nexgen.nxs_utils.Axes import TransformationType
from numpy.typing import DTypeLike

from hyperion.log import NEXUS_LOGGER
from hyperion.utils.utils import convert_eV_to_angstrom


def vds_type_based_on_bit_depth(detector_bit_depth: int) -> DTypeLike:
    """Works out the datatype for the VDS, based on the bit depth from the detector."""
    if detector_bit_depth == 8:
        return np.uint8
    elif detector_bit_depth == 16:
        return np.uint16
    elif detector_bit_depth == 32:
        return np.uint32
    else:
        NEXUS_LOGGER.error(
            f"Unknown detector bit depth {detector_bit_depth}, assuming 16-bit"
        )
        return np.uint16


def create_goniometer_axes(
    omega_start: float,
    scan_points: dict | None,
    x_y_z_increments: tuple[float, float, float] = (0.0, 0.0, 0.0),
    chi: float = 0.0,
    phi: float = 0.0,
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
            "chi", "sam_x", TransformationType.ROTATION, (0.006, -0.0264, 0.9996), chi
        ),
        Axis("phi", "chi", TransformationType.ROTATION, (-1, -0.0025, -0.0056), phi),
    ]
    return Goniometer(gonio_axes, scan_points)


def get_start_and_predicted_end_time(time_expected: float) -> tuple[str, str]:
    time_format = r"%Y-%m-%dT%H:%M:%SZ"
    start = datetime.utcfromtimestamp(time.time())
    end_est = start + timedelta(seconds=time_expected)
    return start.strftime(time_format), end_est.strftime(time_format)


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
    energy_kev: float, flux: float, transmission_fraction: float
) -> tuple[Beam, Attenuator]:
    """Create beam and attenuator objects that nexgen can understands

    Returns:
        tuple[Beam, Attenuator]: Descriptions of the beam and attenuator for nexgen.
    """
    return (
        Beam(convert_eV_to_angstrom(energy_kev * 1000), flux),  # pyright: ignore
        Attenuator(transmission_fraction),  # pyright: ignore
    )
