from __future__ import annotations

import os
from collections.abc import Iterator
from itertools import accumulate
from typing import Annotated

from annotated_types import Len
from dodal.devices.aperturescatterguard import AperturePositionGDANames
from dodal.devices.detector import DetectorParams
from dodal.devices.detector.det_dist_to_beam_converter import (
    DetectorDistanceToBeamXYConverter,
)
from dodal.devices.zebra import (
    RotationDirection,
)
from dodal.log import LOGGER
from pydantic import Field, root_validator, validator
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

DEFAULT_APERTURE_POSITION = AperturePositionGDANames.LARGE_APERTURE


class RotationScanPerSweep(OptionalGonioAngleStarts, OptionalXyzStarts):
    omega_start_deg: float = Field(default=0)  # type: ignore
    rotation_axis: RotationAxis = Field(default=RotationAxis.OMEGA)
    scan_width_deg: float = Field(default=360, gt=0)
    rotation_direction: RotationDirection = Field(default=RotationDirection.NEGATIVE)
    nexus_vds_start_img: int = Field(default=0, ge=0)
    ispyb_extras: TemporaryIspybExtras | None


class RotationExperiment(DiffractionExperimentWithSample):
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

    @validator("selected_aperture")
    def _set_default_aperture_position(
        cls, aperture_position: AperturePositionGDANames | None
    ):
        if not aperture_position:
            LOGGER.warn(
                f"No aperture position selected. Defaulting to {DEFAULT_APERTURE_POSITION}"
            )
            return DEFAULT_APERTURE_POSITION
        else:
            return aperture_position


class RotationScan(WithScan, RotationScanPerSweep, RotationExperiment):
    @property
    def ispyb_params(self):  # pyright: ignore
        return RotationIspybParams(
            visit_path=str(self.visit_directory),
            comment=self.comment,
            xtal_snapshots_omega_start=(
                self.ispyb_extras.xtal_snapshots_omega_start
                if self.ispyb_extras
                else []
            ),
            ispyb_experiment_type=self.ispyb_experiment_type,
            position=None,
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
                self.omega_start_deg
                + (self.scan_width_deg - self.rotation_increment_deg)
            ),
            num=self.num_images,
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    @property
    def num_images(self) -> int:
        return int(self.scan_width_deg / self.rotation_increment_deg)


class MultiRotationScan(RotationExperiment, SplitScan):
    rotation_scans: Annotated[list[RotationScanPerSweep], Len(min_length=1)]

    def _single_rotation_scan(self, scan: RotationScanPerSweep) -> RotationScan:
        # self has everything from RotationExperiment
        params = self.dict()
        del params["rotation_scans"]
        # provided `scan` has everything from RotationScanPerSweep
        params.update(scan.dict())
        # together they have everything for RotationScan
        return RotationScan(**params)

    @root_validator(pre=False)
    def validate_snapshot_directory(cls, values):
        start_img = 0
        for scan in values["rotation_scans"]:
            scan.nexus_vds_start_img = start_img
            start_img += scan.scan_width_deg / values["rotation_increment_deg"]
        return values

    @property
    def single_rotation_scans(self) -> Iterator[RotationScan]:
        for scan in self.rotation_scans:
            yield self._single_rotation_scan(scan)

    def _num_images_per_scan(self):
        return [
            int(scan.scan_width_deg / self.rotation_increment_deg)
            for scan in self.rotation_scans
        ]

    @property
    def num_images(self):
        return sum(self._num_images_per_scan())

    @property
    def scan_indices(self):
        return list(accumulate([0, *self._num_images_per_scan()]))

    @property
    def detector_params(self):
        return self._detector_params(self.rotation_scans[0].omega_start_deg)

    @property
    def ispyb_params(self):  # pyright: ignore
        raise ValueError("Please get ispyb params from one of the individual scans")
