from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Annotated

import numpy as np
from annotated_types import Len
from dodal.devices.detector import DetectorParams
from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)
from dodal.devices.zebra import (
    RotationDirection,
)
from pydantic import Field
from scanspec.core import AxesPoints
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import RotationIspybParams
from hyperion.parameters.components import (
    DiffractionExperimentWithSample,
    IspybExperimentType,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    RotationAxis,
    SplitScan,
    TemporaryIspybExtras,
    WithScan,
)
from hyperion.parameters.constants import CONST, I03Constants


class RotationScanCore(OptionalGonioAngleStarts, OptionalXyzStarts):
    omega_start_deg: float = Field(default=0)  # type: ignore
    rotation_axis: RotationAxis = Field(default=RotationAxis.OMEGA)
    scan_width_deg: float = Field(default=360, gt=0)
    rotation_direction: RotationDirection = Field(default=RotationDirection.NEGATIVE)
    ispyb_extras: TemporaryIspybExtras | None


class RotationScanGeneric(DiffractionExperimentWithSample):
    shutter_opening_time_s: float = Field(default=CONST.I03.SHUTTER_TIME_S)
    rotation_increment_deg: float = Field(default=0.1, gt=0)
    ispyb_experiment_type: IspybExperimentType = Field(
        default=IspybExperimentType.ROTATION
    )

    def _detector_params(self, omega_start_deg: float):
        self.det_dist_to_beam_converter_path = (
            self.det_dist_to_beam_converter_path
            or CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH
        )
        optional_args = {}
        if self.run_number:
            optional_args["run_number"] = self.run_number
        assert self.detector_distance_mm is not None
        os.makedirs(self.storage_directory, exist_ok=True)
        return DetectorParams(
            detector_size_constants=I03Constants.DETECTOR,
            expected_energy_ev=self.demand_energy_ev,
            exposure_time=self.exposure_time_s,
            directory=self.storage_directory,
            prefix=self.file_name,
            detector_distance=self.detector_distance_mm,
            omega_start=omega_start_deg,
            omega_increment=self.rotation_increment_deg,
            num_images_per_trigger=self.num_images,
            num_triggers=1,
            use_roi_mode=False,
            det_dist_to_beam_converter_path=self.det_dist_to_beam_converter_path,
            beam_xy_converter=DetectorDistanceToBeamXYConverter(
                self.det_dist_to_beam_converter_path
            ),
            **optional_args,
        )


class RotationScan(WithScan, RotationScanCore, RotationScanGeneric):
    @property
    def ispyb_params(self):  # pyright: ignore
        pos = np.array([self.x_start_um, self.y_start_um, self.z_start_um])
        return RotationIspybParams(
            visit_path=str(self.visit_directory),
            comment=self.comment,
            xtal_snapshots_omega_start=(
                self.ispyb_extras.xtal_snapshots_omega_start
                if self.ispyb_extras
                else []
            ),
            ispyb_experiment_type=self.ispyb_experiment_type,
            position=pos if np.all(pos) else None,
        )

    @property
    def detector_params(self):
        return self._detector_params(self.omega_start_deg)

    @property
    def scan_points(self) -> AxesPoints:
        scan_spec = Line(
            axis="omega",
            start=self.omega_start_deg,
            stop=(
                self.scan_width_deg + self.omega_start_deg - self.rotation_increment_deg
            ),
            num=self.num_images,
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    @property
    def num_images(self) -> int:
        return int(self.scan_width_deg / self.rotation_increment_deg)


class MultiRotationScan(RotationScanGeneric, SplitScan):
    rotation_scans: Annotated[list[RotationScanCore], Len(min_length=1)]

    def _single_rotation_scan(self, scan: RotationScanCore) -> RotationScan:
        params = self.dict()
        del params["rotation_scans"]
        params.update(scan.dict())
        return RotationScan(**params)

    @property
    def single_rotation_scans(self) -> Iterator[RotationScan]:
        for scan in self.rotation_scans:
            yield self._single_rotation_scan(scan)

    @property
    def num_images(self):
        return sum(
            [
                int(scan.scan_width_deg / self.rotation_increment_deg)
                for scan in self.rotation_scans
            ]
        )

    @property
    def scan_points(self):
        return NotImplemented  # TODO: work out how to make the full scanscpec for this

    @property
    def scan_indices(self):
        return NotImplemented  # TODO: as above

    @property
    def detector_params(self):
        return self._detector_params(self.rotation_scans[0].omega_start_deg)

    @property
    def ispyb_params(self):  # pyright: ignore
        raise ValueError("Please get ispyb params from one of the individual scans")
