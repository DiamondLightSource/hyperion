"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from dodal.utils import get_beamline_name
from nexgen.nxs_utils import Attenuator, Beam, Detector, Goniometer, Source
from nexgen.nxs_write.nxmx_writer import NXmxFileWriter
from numpy.typing import DTypeLike
from scanspec.core import AxesPoints

from hyperion.external_interaction.nexus.nexus_utils import (
    create_detector_parameters,
    create_goniometer_axes,
    get_start_and_predicted_end_time,
)
from hyperion.parameters.components import DiffractionExperimentWithSample


class NexusWriter:
    def __init__(
        self,
        parameters: DiffractionExperimentWithSample,
        data_shape: tuple[int, int, int],
        scan_points: AxesPoints,
        *,
        run_number: int | None = None,
        omega_start_deg: float = 0,
        chi_start_deg: float = 0,
        vds_start_index: int = 0,
    ) -> None:
        self.beam: Optional[Beam] = None
        self.attenuator: Optional[Attenuator] = None
        self.scan_points: dict = scan_points
        self.data_shape: tuple[int, int, int] = data_shape
        self.run_number: int = (
            run_number if run_number else parameters.detector_params.run_number
        )
        self.detector: Detector = create_detector_parameters(parameters.detector_params)
        self.source: Source = Source(get_beamline_name("S03"))
        self.directory: Path = Path(parameters.storage_directory)
        self.filename: str = parameters.file_name
        self.start_index: int = vds_start_index
        self.full_num_of_images: int = parameters.num_images
        self.full_filename: str = parameters.detector_params.full_filename
        self.nexus_file: Path = (
            self.directory / f"{self.filename}_{self.run_number}.nxs"
        )
        self.master_file: Path = (
            self.directory / f"{self.filename}_{self.run_number}_master.h5"
        )
        self.goniometer: Goniometer = create_goniometer_axes(
            omega_start_deg, self.scan_points, chi=chi_start_deg
        )

    def create_nexus_file(self, bit_depth: DTypeLike):
        """
        Creates a nexus file based on the parameters supplied when this object was
        initialised.
        """
        start_time, est_end_time = get_start_and_predicted_end_time(
            self.detector.exp_time * self.full_num_of_images
        )

        assert self.beam is not None
        assert self.attenuator is not None

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
                est_end_time=est_end_time,
            )
            NXmx_Writer.write_vds(
                vds_offset=self.start_index, vds_shape=vds_shape, vds_dtype=bit_depth
            )

    def get_image_datafiles(self, max_images_per_file=1000):
        return [
            self.directory / f"{self.full_filename}_{h5_num + 1:06}.h5"
            for h5_num in range(
                math.ceil(self.full_num_of_images / max_images_per_file)
            )
        ]
