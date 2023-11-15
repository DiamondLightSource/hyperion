from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.det_dim_constants import DetectorSize_pixels
from dodal.devices.detector import TriggerMode
from dodal.devices.fast_grid_scan import GridAxis, GridScanParams
from pydantic import Extra, validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.external_interaction.ispyb.ispyb_dataclass import GridscanIspybParams
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
)


class GridscanInternalParameters(InternalParameters):
    experiment_params: GridScanParams
    ispyb_params: GridscanIspybParams

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **HyperionParameters.Config.json_encoders,
        }
        extra = Extra.ignore

    @classmethod
    def from_external(cls, external: ExternalParameters):
        return cls(
            params_version=external.parameter_version,
            hyperion_params=HyperionParameters.from_external(external),
            ispyb_params=GridscanIspybParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
            experiment_params=GridScanParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
        )

    # @validator("hyperion_params", pre=True)
    # def _preprocess_hyperion_params(
    #     cls, all_params: dict[str, Any], values: dict[str, Any]
    # ):
    #     experiment_params: GridScanParams = values["experiment_params"]
    #     all_params["num_images"] = experiment_params.get_num_images()
    #     all_params["position"] = np.array(all_params["position"])
    #     all_params["omega_increment"] = 0
    #     all_params["num_triggers"] = all_params["num_images"]
    #     all_params["num_images_per_trigger"] = 1
    #     all_params["trigger_mode"] = TriggerMode.FREE_RUN
    #     all_params["upper_left"] = np.array(all_params["upper_left"])
    #     return HyperionParameters.parse_obj(all_params)

    def get_scan_points(self, scan_number: int) -> dict:
        """Get the scan points for the first or second gridscan: scan number must be
        1 or 2"""

        def create_line(name: str, axis: GridAxis):
            return Line(name, axis.start, axis.end, axis.full_steps)

        if scan_number == 1:
            x_line = create_line("sam_x", self.experiment_params.x_axis)
            y_line = create_line("sam_y", self.experiment_params.y_axis)
            spec = y_line * ~x_line
        elif scan_number == 2:
            x_line = create_line("sam_x", self.experiment_params.x_axis)
            z_line = create_line("sam_z", self.experiment_params.z_axis)
            spec = z_line * ~x_line
        else:
            raise Exception("Cannot provide scan points for other scans than 1 or 2")

        scan_path = ScanPath(spec.calculate())
        return scan_path.consume().midpoints

    def get_data_shape(self, scan_points: dict) -> tuple[int, int, int]:
        size: DetectorSize_pixels = (
            self.hyperion_params.detector_params.detector_size_constants.det_size_pixels
        )
        ax = list(scan_points.keys())[0]
        num_frames_in_vds = len(scan_points[ax])
        return (num_frames_in_vds, size.width, size.height)

    def get_omega_start(self, scan_number: int) -> float:
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        detector_params = self.hyperion_params.detector_params
        return detector_params.omega_start + 90 * (scan_number - 1)

    def get_run_number(self, scan_number: int) -> int:
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        detector_params = self.hyperion_params.detector_params
        return detector_params.run_number + (scan_number - 1)

    def get_nexus_info(self, scan_number: int) -> dict:
        """Returns a dict of info necessary for initialising NexusWriter, containing:
        data_shape, scan_points, omega_start, filename
        """
        scan_points = self.get_scan_points(scan_number)
        return {
            "data_shape": self.get_data_shape(scan_points),
            "scan_points": scan_points,
            "omega_start": self.get_omega_start(scan_number),
            "run_number": self.get_run_number(scan_number),
        }
