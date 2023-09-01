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
from nexgen.nxs_utils import Detector, Goniometer, Source
from nexgen.nxs_write.NXmxWriter import NXmxFileWriter

from hyperion.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
    create_detector_parameters,
    create_goniometer_axes,
    get_current_time,
)
from hyperion.parameters.internal_parameters import InternalParameters


class NexusWriter:
    def __init__(
        self,
        parameters: InternalParameters,
        scan_points: dict,
        data_shape: tuple[int, int, int],
        omega_start: float | None = None,
        run_number: int | None = None,
        vds_start_index: int = 0,
    ) -> None:
        self.scan_points: dict = scan_points
        self.data_shape: tuple[int, int, int] = data_shape
        self.omega_start: float = (
            omega_start
            if omega_start
            else parameters.hyperion_params.detector_params.omega_start
        )
        self.run_number: int = (
            run_number
            if run_number
            else parameters.hyperion_params.detector_params.run_number
        )
        self.detector: Detector = create_detector_parameters(
            parameters.hyperion_params.detector_params
        )
        self.beam, self.attenuator = create_beam_and_attenuator_parameters(
            parameters.hyperion_params.ispyb_params
        )
        self.source: Source = Source(parameters.hyperion_params.beamline)
        self.directory: Path = Path(
            parameters.hyperion_params.detector_params.directory
        )
        self.filename: str = parameters.hyperion_params.detector_params.prefix
        self.start_index: int = vds_start_index
        self.full_num_of_images: int = (
            parameters.hyperion_params.detector_params.num_triggers
            * parameters.hyperion_params.detector_params.num_images_per_trigger
        )
        self.full_filename: str = (
            parameters.hyperion_params.detector_params.full_filename
        )
        self.nexus_file: Path = (
            self.directory / f"{self.filename}_{self.run_number}.nxs"
        )
        self.master_file: Path = (
            self.directory / f"{self.filename}_{self.run_number}_master.h5"
        )
        self.goniometer: Goniometer = create_goniometer_axes(
            self.omega_start, self.scan_points
        )

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
                image_filename=f"{self.full_filename}",
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
            self.directory / f"{self.full_filename}_{h5_num + 1:06}.h5"
            for h5_num in range(
                math.ceil(self.full_num_of_images / max_images_per_file)
            )
        ]
