from __future__ import annotations

from functools import cached_property

from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.zebra import (
    RotationDirection,
)
from pydantic import validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GridscanIspybParams,
)
from hyperion.parameters.components import (
    DiffractionExperiment,
    OptionalGonioAngleStarts,
    RotationAxis,
    WithSample,
    WithScan,
    XyzAxis,
    XyzStarts,
)
from hyperion.parameters.constants import CONST


class GridCommon(DiffractionExperiment, OptionalGonioAngleStarts, WithSample):
    grid_width_um = CONST.PARAM.GRIDSCAN.WIDTH_UM
    exposure_time_s: float = CONST.PARAM.GRIDSCAN.EXPOSURE_TIME_S
    use_roi_mode: bool = CONST.PARAM.GRIDSCAN.USE_ROI
    transmission_frac: float = 1


class GridScanWithEdgeDetect(GridCommon, WithSample): ...


class PinTipCentreThenXrayCentre(GridCommon):
    tip_offset_um: float = 0


class RobotLoadThenCentre(GridCommon, WithSample): ...


class SpecifiedGridScan(GridCommon, XyzStarts, WithScan, WithSample):
    @cached_property
    def detector_params(self):
        detector_params = {
            "expected_energy_ev": self.demand_energy_ev,
            "exposure_time": self.exposure_time_s,
            "directory": self.visit_directory / "auto" / str(self.sample_id),
            "prefix": self.file_name,
            "detector_distance": self.detector_distance_mm,
            "omega_start": self.omega_start_deg,
            "omega_increment": 0,
            "num_images_per_trigger": 1,
            "num_triggers": self.num_images,
            "use_roi_mode": self,
            "det_dist_to_beam_converter_path": CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH,
            "run_number": self.run_number,
        }
        return DetectorParams(**detector_params)

    @cached_property
    def ispyb_params(self):
        ispyb_params = {
            "visit_path": self.visit_directory,
            "microns_per_pixel_x": 0,
            "microns_per_pixel_y": 0,
            "position": [0, 0, 0],
            "transmission_fraction": self.transmission_frac,
            "current_energy_ev": self.demand_energy_ev,
            "beam_size_x": 0,
            "beam_size_y": 0,
            "focal_spot_size_x": 0,
            "focal_spot_size_y": 0,
            "comment": self.comment,
            "resolution": 0,
            "sample_id": self.sample_id,
            "sample_barcode": "",
            "flux": 0,
            "undulator_gap": 0,
            "synchrotron_mode": "",
            "slit_gap_size_x": 0,
            "slit_gap_size_y": 0,
            "xtal_snapshots_omega_start": 0,
            "xtal_snapshots_omega_end": 0,
            "ispyb_experiment_type": "",
            "upper_left": [0, 0, 0],
        }
        return GridscanIspybParams(**ispyb_params)


class TwoDGridScan(SpecifiedGridScan):
    demand_energy_ev: float | None = None
    omega_start_deg: float | None = None
    axis_1_step_size_um: float = CONST.PARAM.GRIDSCAN.APERTURE_SIZE
    axis_2_step_size_um: float = CONST.PARAM.GRIDSCAN.APERTURE_SIZE
    axis_1: XyzAxis = XyzAxis.X
    axis_2: XyzAxis = XyzAxis.Y
    axis_1_steps: int
    axis_2_steps: int

    @validator("axis_2")
    def _validate_axis_2(cls, axis_2: XyzAxis, values) -> XyzAxis:
        if axis_2 == values["axis_1"]:
            raise ValueError(
                f"Axis 1 ({values['axis_1']}) and axis 2 ({axis_2}) cannot be equal!"
            )
        return axis_2

    @property
    def normal_axis(self) -> XyzAxis:
        return ({XyzAxis.X, XyzAxis.Y, XyzAxis.Z} ^ {self.axis_1, self.axis_2}).pop()

    @property
    def axis_1_start_um(self) -> float:
        return self.axis_1.for_axis(self.x_start_um, self.y_start_um, self.z_start_um)

    @property
    def axis_2_start_um(self) -> float:
        return self.axis_2.for_axis(self.x_start_um, self.y_start_um, self.z_start_um)

    @property
    def normal_axis_start(self) -> float:
        return self.normal_axis.for_axis(
            self.x_start_um, self.y_start_um, self.z_start_um
        )

    @property
    def axis_1_end_um(self) -> float:
        return self.axis_1_start_um + self.axis_1_step_size_um * self.axis_1_steps

    @property
    def axis_2_end_um(self) -> float:
        return self.axis_2_start_um + self.axis_2_step_size_um * self.axis_2_steps

    @property
    def num_images(self) -> float:
        return self.axis_1_steps * self.axis_2_steps

    @cached_property
    def scan_spec(self):
        line_1 = Line(
            str(self.axis_1.value),
            self.axis_1_start_um,
            self.axis_1_end_um,
            self.axis_1_steps,
        )
        line_2 = Line(
            str(self.axis_2.value),
            self.axis_2_start_um,
            self.axis_2_end_um,
            self.axis_2_steps,
        )
        return line_2 * ~line_1

    @cached_property
    def scan_points(self):
        return ScanPath(self.scan_spec.calculate()).consume().midpoints


class ThreeDGridScan(SpecifiedGridScan):
    demand_energy_ev: float | None = None
    omega_start_deg: float | None = None
    x_step_size_um: float = CONST.PARAM.GRIDSCAN.APERTURE_SIZE
    y_step_size_um: float = CONST.PARAM.GRIDSCAN.APERTURE_SIZE
    z_step_size_um: float = CONST.PARAM.GRIDSCAN.APERTURE_SIZE
    y2_start_um: float
    z2_start_um: float
    x_steps: int
    y_steps: int
    z_steps: int

    @cached_property
    def scan_1(self) -> TwoDGridScan:
        values = self.dict()
        values["y_start"] = self.y_start_um
        values["z_start"] = self.z_start_um
        values["axis_1"] = XyzAxis.X
        values["axis_2"] = XyzAxis.Y
        values["axis_1_steps"] = self.x_steps
        values["axis_2_steps"] = self.y_steps
        return TwoDGridScan(**values)

    @cached_property
    def scan_2(self) -> TwoDGridScan:
        values = self.dict()
        values["y_start"] = self.y2_start_um
        values["z_start"] = self.z2_start_um
        values["axis_1"] = XyzAxis.X
        values["axis_2"] = XyzAxis.Z
        values["axis_1_steps"] = self.x_steps
        values["axis_2_steps"] = self.z_steps
        return TwoDGridScan(**values)

    def FGS_params(self) -> GridScanParams:
        return GridScanParams(
            x_steps=self.x_steps,
            y_steps=self.y_steps,
            z_steps=self.z_steps,
            x_step_size=self.x_step_size_um,
            y_step_size=self.y_step_size_um,
            z_step_size=self.z_step_size_um,
            x_start=self.scan_1.axis_1_start_um,
            y1_start=self.scan_1.axis_2_start_um,
            z1_start=self.scan_1.normal_axis_start,
            y2_start=self.scan_2.normal_axis_start,
            z2_start=self.scan_2.axis_2_start_um,
            set_stub_offsets=False,
            dwell_time_ms=self.exposure_time_s,
        )

    @property
    def num_images(self) -> float:
        return self.scan_1.num_images + self.scan_2.num_images

    @cached_property
    def scan_points(self):
        # TODO: requires making the points for the 2D scans 3D points
        return NotImplemented


# Doesn't yet exist but will look something like this
class DoOneUDC(GridCommon):
    """Diffraction data is for grids at start"""

    rotation_exposure_s: float
    rotation_axis: RotationAxis = RotationAxis.OMEGA
    rotation_angle_deg: float
    rotation_increment_deg: float
    rotation_direction: RotationDirection
