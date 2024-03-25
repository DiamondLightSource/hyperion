from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np
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
    TemporaryIspybExtras,
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
    # field rather than inherited to make it easier to track when it can be removed:
    ispyb_extras: TemporaryIspybExtras = TemporaryIspybExtras()


class GridScanWithEdgeDetect(GridCommon, WithSample): ...


class PinTipCentreThenXrayCentre(GridCommon):
    tip_offset_um: float = 0


class RobotLoadThenCentre(GridCommon, WithSample): ...


class SpecifiedGridScan(GridCommon, XyzStarts, WithScan, WithSample):
    @property
    def detector_params(self):
        detector_params = {
            "expected_energy_ev": self.demand_energy_ev,
            "exposure_time": self.exposure_time_s,
            "directory": str(
                self.visit_directory / "xraycentring" / str(self.sample_id)
            ),
            "prefix": self.file_name,
            "detector_distance": self.detector_distance_mm,
            "omega_start": self.omega_start_deg,
            "omega_increment": 0,
            "num_images_per_trigger": 1,
            "num_triggers": self.num_images,
            "use_roi_mode": self.use_roi_mode,
            "det_dist_to_beam_converter_path": self.det_dist_to_beam_converter_path,
            "run_number": self.run_number,
            "trigger_mode": self.trigger_mode,
        }
        return DetectorParams(**detector_params)

    @property
    def ispyb_params(  # pyright: ignore # cached_property[T] doesn't check subtypes of T
        self,
    ):
        assert self.ispyb_extras.microns_per_pixel_x is not None
        assert self.ispyb_extras.microns_per_pixel_y is not None
        assert self.ispyb_extras.beam_size_x is not None
        assert self.ispyb_extras.beam_size_y is not None
        assert self.ispyb_extras.focal_spot_size_x is not None
        assert self.ispyb_extras.focal_spot_size_y is not None
        assert self.sample_id is not None
        assert self.ispyb_extras.xtal_snapshots_omega_start is not None
        assert self.ispyb_extras.xtal_snapshots_omega_end is not None
        return GridscanIspybParams(
            visit_path=str(self.visit_directory),
            microns_per_pixel_x=self.ispyb_extras.microns_per_pixel_x,
            microns_per_pixel_y=self.ispyb_extras.microns_per_pixel_y,
            position=np.array(self.ispyb_extras.position),
            transmission_fraction=self.transmission_frac,
            current_energy_ev=self.demand_energy_ev,
            beam_size_x=self.ispyb_extras.beam_size_x,
            beam_size_y=self.ispyb_extras.beam_size_y,
            focal_spot_size_x=self.ispyb_extras.focal_spot_size_x,
            focal_spot_size_y=self.ispyb_extras.focal_spot_size_y,
            comment=self.comment,
            resolution=self.ispyb_extras.resolution,
            sample_id=str(self.sample_id),
            sample_barcode=self.ispyb_extras.sample_barcode,
            flux=self.ispyb_extras.flux,
            undulator_gap=self.ispyb_extras.undulator_gap,
            synchrotron_mode=self.ispyb_extras.synchrotron_mode,
            slit_gap_size_x=self.ispyb_extras.slit_gap_size_x,
            slit_gap_size_y=self.ispyb_extras.slit_gap_size_x,
            xtal_snapshots_omega_start=self.ispyb_extras.xtal_snapshots_omega_start,
            xtal_snapshots_omega_end=self.ispyb_extras.xtal_snapshots_omega_end,
            ispyb_experiment_type=self.ispyb_extras.ispyb_experiment_type,
            upper_left=np.array(self.ispyb_extras.upper_left),
        )


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
    def num_images(self) -> int:
        return self.axis_1_steps * self.axis_2_steps

    @property
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

    @property
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

    def _delete_excess(self, values: dict[str, Any]):
        del values["x_step_size_um"]
        del values["x_steps"]
        del values["y2_start_um"]
        del values["y_step_size_um"]
        del values["y_steps"]
        del values["z2_start_um"]
        del values["z_step_size_um"]
        del values["z_steps"]

    @property
    @cache
    def scan_1(self) -> TwoDGridScan:
        values = self.dict()
        values["y_start_um"] = self.y_start_um
        values["z_start_um"] = self.z_start_um
        values["axis_1"] = XyzAxis.X
        values["axis_2"] = XyzAxis.Y
        values["axis_1_steps"] = self.x_steps
        values["axis_2_steps"] = self.y_steps
        self._delete_excess(values)
        return TwoDGridScan(**values)

    @property
    @cache
    def scan_2(self) -> TwoDGridScan:
        values = self.dict()
        values["y_start_um"] = self.y2_start_um
        values["z_start_um"] = self.z2_start_um
        values["axis_1"] = XyzAxis.X
        values["axis_2"] = XyzAxis.Z
        values["axis_1_steps"] = self.x_steps
        values["axis_2_steps"] = self.z_steps
        self._delete_excess(values)
        return TwoDGridScan(**values)

    def FGS_params(self) -> GridScanParams:
        return GridScanParams(
            x_steps=self.x_steps,
            y_steps=self.y_steps,
            z_steps=self.z_steps,
            x_step_size=self.x_step_size_um,
            y_step_size=self.y_step_size_um,
            z_step_size=self.z_step_size_um,
            x_start=self.scan_1.axis_1_start_um,  # pyright: ignore # bug in pyright https://github.com/microsoft/pyright/issues/6456
            y1_start=self.scan_1.axis_2_start_um,  # pyright: ignore
            z1_start=self.scan_1.normal_axis_start,  # pyright: ignore
            y2_start=self.scan_2.normal_axis_start,  # pyright: ignore
            z2_start=self.scan_2.axis_2_start_um,  # pyright: ignore
            set_stub_offsets=False,
            dwell_time_ms=self.exposure_time_s,
        )

    @property
    def num_images(self) -> int:
        return self.scan_1.num_images + self.scan_2.num_images  # pyright: ignore

    @property
    @cache
    def scan_points(self):  # pyright: ignore
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
