"""
Define beamline parameters for I03, Eiger detector and give an example of writing a
gridscan.
"""
from __future__ import annotations

import math
import shutil
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Dict, Tuple

import h5py
import numpy as np
from dodal.devices.fast_grid_scan import GridAxis
from nexgen.nxs_utils import (
    Attenuator,
    Beam,
    Detector,
    EigerDetector,
    Goniometer,
    Source,
)
from nexgen.nxs_write.NXmxWriter import NXmxFileWriter
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from artemis.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
    create_detector_parameters,
    create_gridscan_goniometer_axes,
    create_rotation_goniometer_axes,
    get_current_time,
)
from artemis.parameters.internal_parameters import InternalParameters
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


class NexusWriter(ABC):
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

    def __init__(
        self,
        parameters: InternalParameters,
    ) -> None:
        self.detector = create_detector_parameters(
            parameters.artemis_params.detector_params
        )
        self.beam, self.attenuator = create_beam_and_attenuator_parameters(
            parameters.artemis_params.ispyb_params
        )
        self.source = Source(parameters.artemis_params.beamline)
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

    @abstractmethod
    def _get_data_shape_for_vds(self) -> tuple[int | float, ...]:
        ...

    def create_nexus_file(self):
        """
        Creates a nexus file based on the parameters supplied when this obect was
        initialised.
        """
        start_time = get_current_time()

        vds_shape = self._get_data_shape_for_vds()

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


class FGSNexusWriter(NexusWriter):
    grid_scan: dict

    def __init__(self, parameters: FGSInternalParameters, grid_scan: dict) -> None:
        super().__init__(parameters)
        self.goniometer = create_gridscan_goniometer_axes(
            parameters.artemis_params.detector_params,
            parameters.experiment_params,
            grid_scan,
        )
        self.grid_scan = grid_scan

    def _get_data_shape_for_vds(self) -> tuple[int | float, ...]:
        ax = list(self.grid_scan.keys())[0]
        num_frames_in_vds = len(self.grid_scan[ax])
        nexus_detector_params: EigerDetector = self.detector.detector_params
        return (num_frames_in_vds, *nexus_detector_params.image_size)


class RotationNexusWriter(NexusWriter):
    def __init__(self, parameters: RotationInternalParameters) -> None:
        super().__init__(parameters)
        self.goniometer = create_rotation_goniometer_axes(
            parameters.artemis_params.detector_params, parameters.experiment_params
        )

    def _get_data_shape_for_vds(self) -> tuple[int | float, ...]:
        return (1,)
        # ax = list(self.grid_scan.keys())[0]
        # num_frames_in_vds = len(self.grid_scan[ax])
        # return (num_frames_in_vds, *self.detector.detector_params.image_size)


def create_parameters_for_first_file(
    parameters: FGSInternalParameters,
) -> Tuple[FGSInternalParameters, Dict]:
    new_params = deepcopy(parameters)
    new_params.experiment_params.z_axis = GridAxis(
        parameters.experiment_params.z1_start, 0, 0
    )
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
    parameters: FGSInternalParameters,
) -> Tuple[FGSInternalParameters, Dict]:
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


def create_3d_gridscan_writers(
    parameters: FGSInternalParameters,
) -> tuple[NexusWriter, NexusWriter]:
    params_for_first = create_parameters_for_first_file(parameters)
    params_for_second = create_parameters_for_second_file(parameters)
    nexus_writer_1 = FGSNexusWriter(*params_for_first)
    nexus_writer_2 = FGSNexusWriter(*params_for_second)
    return nexus_writer_1, nexus_writer_2
