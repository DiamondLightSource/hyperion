"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""
from __future__ import annotations

import time
from datetime import datetime

from dodal.devices.detector import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from nexgen.nxs_utils import Attenuator, Axis, Beam, Detector, EigerDetector, Goniometer

from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams


def create_goniometer_axes(
    detector_params: DetectorParams,
    experiment_params: AbstractExperimentParameterBase,
    scan_spec: dict,
):
    return Goniometer(gonio_axes, grid_scan)


def get_current_time():
    return datetime.utcfromtimestamp(time.time()).strftime(r"%Y-%m-%dT%H:%M:%SZ")


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
