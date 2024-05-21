from __future__ import annotations

import os

import numpy as np
from dodal.devices.detector import (
    DetectorDistanceToBeamXYConverter,
    DetectorParams,
)
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from pydantic import Field
from scanspec.core import Path as ScanPath
from scanspec.specs import Line, Static

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
)
from hyperion.parameters.components import (
    DiffractionExperiment,
    OptionalGonioAngleStarts,
    SplitScan,
    TemporaryIspybExtras,
    WithOavCentring,
    WithSample,
    WithScan,
    XyzStarts,
)
from hyperion.parameters.constants import CONST


class GridCommon(
    DiffractionExperiment, OptionalGonioAngleStarts, WithSample, WithOavCentring
):
    grid_width_um: float = Field(default=CONST.PARAM.GRIDSCAN.WIDTH_UM)
    exposure_time_s: float = Field(default=CONST.PARAM.GRIDSCAN.EXPOSURE_TIME_S)
    use_roi_mode: bool = Field(default=CONST.PARAM.GRIDSCAN.USE_ROI)
    transmission_frac: float = Field(default=1)
    panda_runup_distance_mm: float = Field(
        default=CONST.HARDWARE.PANDA_FGS_RUN_UP_DEFAULT
    )
    set_stub_offsets: bool = Field(default=False)
    use_panda: bool = Field(default=CONST.I03.USE_PANDA_FOR_GRIDSCAN)
    # field rather than inherited to make it easier to track when it can be removed:
    ispyb_extras: TemporaryIspybExtras

    @property
    def ispyb_params(self):
        return GridscanIspybParams(
            visit_path=str(self.visit_directory),
            position=np.array(self.ispyb_extras.position),
            beam_size_x=self.ispyb_extras.beam_size_x,
            beam_size_y=self.ispyb_extras.beam_size_y,
            focal_spot_size_x=self.ispyb_extras.focal_spot_size_x,
            focal_spot_size_y=self.ispyb_extras.focal_spot_size_y,
            comment=self.comment,
            sample_id=self.sample_id,
            undulator_gap=self.ispyb_extras.undulator_gap,
            xtal_snapshots_omega_start=self.ispyb_extras.xtal_snapshots_omega_start
            or [],
            xtal_snapshots_omega_end=self.ispyb_extras.xtal_snapshots_omega_end or [],
            ispyb_experiment_type=self.ispyb_experiment_type,
        )

    @property
    def detector_params(self):
        self.det_dist_to_beam_converter_path = (
            self.det_dist_to_beam_converter_path
            or CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH
        )
        optional_args = {}
        if self.run_number:
            optional_args["run_number"] = self.run_number
        assert (
            self.detector_distance_mm is not None
        ), "Detector distance must be filled before generating DetectorParams"
        os.makedirs(self.storage_directory, exist_ok=True)
        return DetectorParams(
            detector_size_constants=self.detector,  # type: ignore # Will be cleaned up in #1307
            expected_energy_ev=self.demand_energy_ev,
            exposure_time=self.exposure_time_s,
            directory=self.storage_directory,
            prefix=self.file_name,
            detector_distance=self.detector_distance_mm,
            omega_start=self.omega_start_deg or 0,
            omega_increment=0,
            num_images_per_trigger=1,
            num_triggers=self.num_images,
            use_roi_mode=self.use_roi_mode,
            det_dist_to_beam_converter_path=self.det_dist_to_beam_converter_path,
            trigger_mode=self.trigger_mode,
            beam_xy_converter=DetectorDistanceToBeamXYConverter(
                self.det_dist_to_beam_converter_path
            ),
            **optional_args,
        )


class GridScanWithEdgeDetect(GridCommon, WithSample): ...


class PinTipCentreThenXrayCentre(GridCommon):
    tip_offset_um: float = 0


class RobotLoadThenCentre(GridCommon, WithSample):
    def pin_centre_then_xray_centre_params(self):
        params = PinTipCentreThenXrayCentre(**self.dict())
        return params


class SpecifiedGridScan(GridCommon, XyzStarts, WithScan, WithSample):
    """A specified grid scan is one which has defined values for the start position,
    grid and box sizes, etc., as opposed to parameters for a plan which will create
    those parameters at some point (e.g. through optical pin detection)."""

    ...


class ThreeDGridScan(SpecifiedGridScan, SplitScan):
    """Parameters representing a so-called 3D grid scan, which consists of doing a
    gridscan in X and Y, followed by one in X and Z."""

    demand_energy_ev: float | None = Field(default=None)
    grid1_omega_deg: float = Field(default=CONST.PARAM.GRIDSCAN.OMEGA_1)  # type: ignore
    grid2_omega_deg: float = Field(default=CONST.PARAM.GRIDSCAN.OMEGA_2)
    x_step_size_um: float = Field(default=CONST.PARAM.GRIDSCAN.BOX_WIDTH_UM)
    y_step_size_um: float = Field(default=CONST.PARAM.GRIDSCAN.BOX_WIDTH_UM)
    z_step_size_um: float = Field(default=CONST.PARAM.GRIDSCAN.BOX_WIDTH_UM)
    y2_start_um: float
    z2_start_um: float
    x_steps: int = Field(gt=0)
    y_steps: int = Field(gt=0)
    z_steps: int = Field(gt=0)

    @property
    def FGS_params(self) -> GridScanParams:
        return GridScanParams(
            x_steps=self.x_steps,
            y_steps=self.y_steps,
            z_steps=self.z_steps,
            x_step_size=self.x_step_size_um,
            y_step_size=self.y_step_size_um,
            z_step_size=self.z_step_size_um,
            x_start=self.x_start_um,
            y1_start=self.y_start_um,
            z1_start=self.z_start_um,
            y2_start=self.y2_start_um,
            z2_start=self.z2_start_um,
            set_stub_offsets=False,
            dwell_time_ms=self.exposure_time_s * 1000,
            transmission_fraction=self.transmission_frac,
        )

    @property
    def panda_FGS_params(self) -> PandAGridScanParams:
        if self.y_steps % 2 and self.z_steps > 0:
            raise OddYStepsException(
                "The number of Y steps must be even for a PandA gridscan"
            )
        return PandAGridScanParams(
            x_steps=self.x_steps,
            y_steps=self.y_steps,
            z_steps=self.z_steps,
            x_step_size=self.x_step_size_um,
            y_step_size=self.y_step_size_um,
            z_step_size=self.z_step_size_um,
            x_start=self.x_start_um,
            y1_start=self.y_start_um,
            z1_start=self.z_start_um,
            y2_start=self.y2_start_um,
            z2_start=self.z2_start_um,
            set_stub_offsets=False,
            run_up_distance_mm=self.panda_runup_distance_mm,
            transmission_fraction=self.transmission_frac,
        )

    @property
    def grid_1_spec(self):
        x_end = self.x_start_um + self.x_step_size_um * (self.x_steps - 1)
        y1_end = self.y_start_um + self.y_step_size_um * (self.y_steps - 1)
        grid_1_x = Line("sam_x", self.x_start_um, x_end, self.x_steps)
        grid_1_y = Line("sam_y", self.y_start_um, y1_end, self.y_steps)
        grid_1_z = Static("sam_z", self.z_start_um)
        return grid_1_y.zip(grid_1_z) * ~grid_1_x

    @property
    def grid_2_spec(self):
        x_end = self.x_start_um + self.x_step_size_um * (self.x_steps - 1)
        z2_end = self.z2_start_um + self.z_step_size_um * (self.z_steps - 1)
        grid_2_x = Line("sam_x", self.x_start_um, x_end, self.x_steps)
        grid_2_z = Line("sam_z", self.z2_start_um, z2_end, self.z_steps)
        grid_2_y = Static("sam_y", self.y2_start_um)
        return grid_2_z.zip(grid_2_y) * ~grid_2_x

    @property
    def scan_indices(self):
        """The first index of each gridscan, useful for writing nexus files/VDS"""
        return [
            0,
            len(ScanPath(self.grid_1_spec.calculate()).consume().midpoints["sam_x"]),
        ]

    @property
    def scan_spec(self):
        """A fully specified ScanSpec object representing both grids, with x, y, z and
        omega positions."""
        return self.grid_1_spec.concat(self.grid_2_spec)

    @property
    def scan_points(self):
        """A list of all the points in the scan_spec."""
        return ScanPath(self.scan_spec.calculate()).consume().midpoints

    @property
    def scan_points_1(self):
        """A list of all the points in the first grid scan."""
        return ScanPath(self.grid_1_spec.calculate()).consume().midpoints

    @property
    def scan_points_2(self):
        """A list of all the points in the second grid scan."""
        return ScanPath(self.grid_2_spec.calculate()).consume().midpoints

    @property
    def num_images(self) -> int:
        return len(self.scan_points["sam_x"])


class OddYStepsException(Exception): ...
