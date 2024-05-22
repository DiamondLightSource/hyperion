from __future__ import annotations

import os

import numpy as np
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
    TemporaryIspybExtras,
    WithScan,
)
from hyperion.parameters.constants import CONST


class RotationScan(
    DiffractionExperimentWithSample,
    WithScan,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
):
    omega_start_deg: float = Field(default=0)  # type: ignore
    rotation_axis: RotationAxis = Field(default=RotationAxis.OMEGA)
    shutter_opening_time_s: float = Field(default=CONST.I03.SHUTTER_TIME_S)
    scan_width_deg: float = Field(default=360, gt=0)
    rotation_increment_deg: float = Field(default=0.1, gt=0)
    rotation_direction: RotationDirection = Field(default=RotationDirection.NEGATIVE)
    ispyb_experiment_type: IspybExperimentType = Field(
        default=IspybExperimentType.ROTATION
    )
    transmission_frac: float
    ispyb_extras: TemporaryIspybExtras

    @property
    def detector_params(self):
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
            expected_energy_ev=self.demand_energy_ev,
            exposure_time=self.exposure_time_s,
            directory=self.storage_directory,
            prefix=self.file_name,
            detector_distance=self.detector_distance_mm,
            omega_start=self.omega_start_deg,
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

    @property
    def ispyb_params(self):  # pyright: ignore
        return RotationIspybParams(
            visit_path=str(self.visit_directory),
            position=np.array(self.ispyb_extras.position),
            comment=self.comment,
            xtal_snapshots_omega_start=self.ispyb_extras.xtal_snapshots_omega_start,
            xtal_snapshots_omega_end=self.ispyb_extras.xtal_snapshots_omega_end,
            ispyb_experiment_type=self.ispyb_experiment_type,
        )

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
