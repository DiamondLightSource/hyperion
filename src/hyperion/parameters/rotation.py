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
    DiffractionExperiment,
    IspybExperimentType,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    RotationAxis,
    TemporaryIspybExtras,
    WithSample,
    WithScan,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationHyperionParameters,
    RotationInternalParameters,
    RotationScanParams,
)


class RotationScan(
    DiffractionExperiment,
    WithScan,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    WithSample,
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
            beam_size_x=self.ispyb_extras.beam_size_x,
            beam_size_y=self.ispyb_extras.beam_size_y,
            focal_spot_size_x=self.ispyb_extras.focal_spot_size_x,
            focal_spot_size_y=self.ispyb_extras.focal_spot_size_y,
            comment=self.comment,
            sample_id=str(self.sample_id),
            undulator_gap=self.ispyb_extras.undulator_gap,
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

    # Can be removed in #1277
    def old_parameters(self) -> RotationInternalParameters:
        return RotationInternalParameters(
            params_version=str(self.parameter_model_version),  # type: ignore
            experiment_params=RotationScanParams(
                rotation_axis=self.rotation_axis,
                rotation_angle=self.scan_width_deg,
                image_width=self.rotation_increment_deg,
                omega_start=self.omega_start_deg,
                phi_start=self.phi_start_deg,
                chi_start=self.chi_start_deg,
                kappa_start=self.kappa_start_deg,
                x=self.x_start_um,
                y=self.y_start_um,
                z=self.z_start_um,
                rotation_direction=self.rotation_direction,
                shutter_opening_time_s=self.shutter_opening_time_s,
                transmission_fraction=self.transmission_frac,
            ),
            hyperion_params=RotationHyperionParameters(
                zocalo_environment=self.zocalo_environment,
                beamline=self.beamline,
                insertion_prefix=self.insertion_prefix,
                experiment_type="SAD",
                detector_params=self.detector_params,
                ispyb_params=self.ispyb_params,
            ),
        )
