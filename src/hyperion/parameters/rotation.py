from __future__ import annotations

from functools import cache

from dodal.devices.detector import DetectorParams
from dodal.devices.zebra import (
    RotationDirection,
)
from scanspec.core import AxesPoints
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import RotationIspybParams
from hyperion.parameters.components import (
    DiffractionExperiment,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    RotationAxis,
    WithSample,
    WithScan,
)
from hyperion.parameters.constants import CONST


class RotationScan(
    DiffractionExperiment,
    WithScan,
    OptionalGonioAngleStarts,
    OptionalXyzStarts,
    WithSample,
):
    omega_start_deg: float = 0  # type: ignore
    rotation_axis: RotationAxis = RotationAxis.OMEGA
    rotation_angle_deg: float
    rotation_increment_deg: float
    rotation_direction: RotationDirection
    transmission_frac: float

    @property
    @cache
    def detector_params(self):
        assert (
            self._puck is not None and self._pin is not None
        ), "Must fill puck and pin details before using"
        params = {
            "expected_energy_ev": self.demand_energy_ev,
            "exposure_time": self.exposure_time_s,
            "directory": self.visit_directory / "auto" / str(self.sample_id),
            "prefix": self.file_name,
            "detector_distance": self.detector_distance_mm,
            "omega_start": self.omega_start_deg,
            "omega_increment": self.rotation_increment_deg,
            "num_images_per_trigger": 0,
            "num_triggers": 1,
            "use_roi_mode": False,
            "det_dist_to_beam_converter_path": CONST.PARAM.DETECTOR.BEAM_XY_LUT_PATH,
            "run_number": self.run_number,
        }
        return DetectorParams(**params)

    @property
    @cache
    def ispyb_params(self):  # pyright: ignore
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
            "ispyb_experiment_type": "SAD",
            "upper_left": [0, 0, 0],
        }
        return RotationIspybParams(**ispyb_params)

    @property
    @cache
    def scan_points(self) -> AxesPoints:
        scan_spec = Line(
            axis="omega",
            start=self.omega_start_deg,
            stop=(self.rotation_angle_deg + self.omega_start_deg),
            num=self.num_images,
        )
        scan_path = ScanPath(scan_spec.calculate())
        return scan_path.consume().midpoints

    @property
    def num_images(self) -> int:
        return int(self.rotation_angle_deg / self.rotation_increment_deg)
