"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import h5py
import numpy as np
from nexgen.nxs_utils import Attenuator, Beam, Detector, Goniometer, Source
from nexgen.nxs_write.NXmxWriter import NXmxFileWriter

from artemis.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
    create_detector_parameters,
    create_goniometer_axes,
    get_current_time,
)
from artemis.parameters.internal_parameters import InternalParameters


class NexusWriter:
    detector: Detector
    source: Source
    beam: Beam
    attenuator: Attenuator
    goniometer: Goniometer
    directory: Path
    start_index: int
    full_num_of_images: int
    nexus_file: Path
    master_file: Path
    scan_points: dict
    data_shape: tuple[int, int, int]
    omega_start: float

    def __init__(
        self,
        parameters: InternalParameters,
        scan_points: dict,
        data_shape: tuple[int, int, int],
        omega_start: float | None = None,
        filename: str | None = None,
    ) -> None:
        self.scan_points = scan_points
        self.data_shape = data_shape
        self.omega_start = (
            omega_start
            if omega_start
            else parameters.artemis_params.detector_params.omega_start
        )
        self.detector = create_detector_parameters(
            parameters.artemis_params.detector_params
        )
        self.beam, self.attenuator = create_beam_and_attenuator_parameters(
            parameters.artemis_params.ispyb_params
        )
        self.source = Source(parameters.artemis_params.beamline)
        self.directory = Path(parameters.artemis_params.detector_params.directory)
        self.filename = (
            filename
            if filename
            else parameters.artemis_params.detector_params.full_filename
        )
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
        self.goniometer = create_goniometer_axes(self.omega_start, self.scan_points)

    def create_nexus_file(self):
        """
        Creates a nexus file based on the parameters supplied when this obect was
        initialised.
        """
        start_time = get_current_time()

        vds_shape = self.data_shape

        for filename in [self.nexus_file, self.master_file]:
            NXmx_Writer = NXmxFileWriter(
                filename,
                self.goniometer,
                self.detector,
                self.source,
                self.beam,
                self.attenuator,
                self.full_num_of_images,
            )
            NXmx_Writer.write(
                image_filename=self.filename,
                start_time=start_time,
            )
            NXmx_Writer.write_vds(
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
                    "end_time", data=np.string_(get_current_time())
                )
            shutil.move(temp_filename, filename)

    def get_image_datafiles(self, max_images_per_file=1000):
        return [
            self.directory / f"{self.filename}_{h5_num + 1:06}.h5"
            for h5_num in range(
                math.ceil(self.full_num_of_images / max_images_per_file)
            )
        ]
