"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""
from __future__ import annotations

import math
import shutil
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import h5py
import numpy as np
from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridAxis, GridScanParams

#
from nexgen.nxs_utils import (
    Attenuator,
    Axis,
    Beam,
    Detector,
    EigerDetector,
    Goniometer,
    Source,
)
from nexgen.nxs_write.NXmxWriter import NXmxFileWriter

# from nexgen.nxs_write.NexusWriter import ScanReader, call_writers
# from nexgen.nxs_write.NXclassWriters import write_NXentry
# from nexgen.tools.VDS_tools import image_vds_writer
from numpy.typing import ArrayLike
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams
from artemis.parameters.internal_parameters import InternalParameters


def create_parameters_for_first_file(
    parameters: InternalParameters,
) -> Tuple[InternalParameters, Dict]:
    new_params = deepcopy(parameters)
    new_params.experiment_params.z_axis = GridAxis(
        parameters.experiment_params.z1_start, 0, 0
    )
    # new_params.artemis_params.detector_params.num_triggers = (
    #    parameters.experiment_params.x_steps * parameters.experiment_params.y_steps
    # )
    new_params.artemis_params.detector_params.nexus_file_run_number = (
        parameters.artemis_params.detector_params.run_number
    )

    spec = Line(
        "sam_y",
        new_params.experiment_params.y_axis.start,
        new_params.experiment_params.y_axis.end,
        new_params.experiment_params.y_steps,
    ) * ~Line(
        "sam_x",
        new_params.experiment_params.x_axis.start,
        new_params.experiment_params.x_axis.end,
        new_params.experiment_params.x_steps,
    )
    scan_path = ScanPath(spec.calculate())

    return new_params, scan_path.consume().midpoints


def create_parameters_for_second_file(
    parameters: InternalParameters,
) -> Tuple[InternalParameters, Dict]:
    new_params = deepcopy(parameters)
    new_params.experiment_params.y_axis = GridAxis(
        parameters.experiment_params.y2_start, 0, 0
    )
    new_params.artemis_params.detector_params.omega_start += 90
    new_params.artemis_params.detector_params.nexus_file_run_number = (
        parameters.artemis_params.detector_params.run_number + 1
    )
    new_params.artemis_params.detector_params.start_index = (
        parameters.experiment_params.x_steps * parameters.experiment_params.y_steps
    )

    spec = Line(
        "sam_z",
        new_params.experiment_params.z_axis.start,
        new_params.experiment_params.z_axis.end,
        new_params.experiment_params.z_steps,
    ) * ~Line(
        "sam_x",
        new_params.experiment_params.x_axis.start,
        new_params.experiment_params.x_axis.end,
        new_params.experiment_params.x_steps,
    )
    scan_path = ScanPath(spec.calculate())

    return new_params, scan_path.consume().midpoints


def create_goniometer_axes(
    detector_params: DetectorParams, grid_scan_params: GridScanParams, grid_scan: Dict
) -> Goniometer:
    """Create the data for the goniometer.

    Args:
        detector_params (DetectorParams): Information about the detector.

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


def create_detector_parameters(detector_params: DetectorParams) -> Detector:
    """Returns the detector information in a format that nexgen wants.

    Args:
        detector_params (DetectorParams): The detector params as Artemis stores them.

    Returns:
        Detector: Detector description for nexgen.
    """
    detector_pixels = detector_params.get_detector_size_pizels()

    detector_params = EigerDetector(
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
        detector_params,
        detector_axes,
        detector_params.get_beam_position_pixels(detector_params.detector_distance),
        detector_params.exposure_time,
        [(-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)],
    )


def create_beam_and_attenuator_parameters(
    ispyb_params: IspybParams,
) -> Tuple[Beam, Attenuator]:
    """Create beam and attenuator dictionaries that nexgen can understand.

    Args:
        ispyb_params (IspybParams): An IspybParams object holding all required data.

    Returns:
        Tuple[Beam, Attenuator]: Descriptions of the beam and attenuator for nexgen.
    """
    return (
        Beam(ispyb_params.wavelength, ispyb_params.flux),
        Attenuator(ispyb_params.transmission),
    )


class NexusWriter:
    def __init__(
        self,
        parameters: InternalParameters,
        grid_scan: Dict[str, ArrayLike],
    ) -> None:
        self.grid_scan = grid_scan

        self.detector = create_detector_parameters(
            parameters.artemis_params.detector_params
        )
        self.beam, self.attenuator = create_beam_and_attenuator_parameters(
            parameters.artemis_params.ispyb_params
        )

        self.goniometer = create_goniometer_axes(
            parameters.artemis_params.detector_params,
            parameters.experiment_params,
            grid_scan,
        )

        self.source = Source("I03")

        self.directory = Path(parameters.artemis_params.detector_params.directory)
        self.filename = parameters.artemis_params.detector_params.full_filename

        self.start_index = parameters.artemis_params.detector_params.start_index

        self.full_num_of_images = (
            parameters.artemis_params.detector_params.num_triggers
            * parameters.artemis_params.detector_params.num_images_per_trigger
        )

        self.nexus_file = (
            self.directory
            / f"{parameters.artemis_params.detector_params.nexus_filename}.nxs"
        )
        self.master_file = (
            self.directory
            / f"{parameters.artemis_params.detector_params.nexus_filename}_master.h5"
        )

    def _get_current_time(self):
        return datetime.utcfromtimestamp(time.time()).strftime(r"%Y-%m-%dT%H:%M:%SZ")

    def _get_data_shape_for_vds(self):
        ax = list(self.grid_scan.keys())[0]
        num_frames_in_vds = len(self.grid_scan[ax])
        return (num_frames_in_vds, *self.detector.detector_params.image_size)

    def get_image_datafiles(self):
        max_images_per_file = 1000
        return [
            self.directory / f"{self.filename}_{h5_num + 1:06}.h5"
            for h5_num in range(
                math.ceil(self.full_num_of_images / max_images_per_file)
            )
        ]

    def create_nexus_file(self):
        """
        Creates a nexus file based on the parameters supplied when this obect was
        initialised.
        """
        start_time = self._get_current_time()

        vds_shape = self._get_data_shape_for_vds()

        for filename in [self.nexus_file, self.master_file]:
            NXmxWriter = NXmxFileWriter(
                filename,
                self.goniometer,
                self.detector,
                self.source,
                self.beam,
                self.attenuator,
                self.full_num_of_images,
            )
            NXmxWriter.write(
                image_filename=self.filename,
                start_time=start_time,
            )
            NXmxWriter.write_vds(
                vds_offset=self.start_index,
                vds_shape=vds_shape,
            )

    def update_nexus_file_timestamp(self):
        """
        Write timestamp when finishing run.
        For the nexus file to be updated atomically, changes are written to a
        temporary copy which then replaces the original.
        """
        for filename in [self.nexus_file, self.master_file]:
            temp_filename = filename.parent / f"{filename.name}.tmp"
            shutil.copy(filename, temp_filename)
            with h5py.File(temp_filename, "r+") as nxsfile:
                nxsfile["entry"].create_dataset(
                    "end_time", data=np.string_(self._get_current_time())
                )
            shutil.move(temp_filename, filename)
