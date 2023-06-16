from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import TriggerMode
from dodal.devices.fast_grid_scan import GridScanParams
from pydantic import validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


class FGSInternalParameters(InternalParameters):
    experiment_params: GridScanParams
    artemis_params: ArtemisParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **ArtemisParameters.Config.json_encoders,
        }

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        return GridScanParams(
            **extract_experiment_params_from_flat_dict(
                GridScanParams, experiment_params
            )
        )

    @validator("artemis_params", pre=True)
    def _preprocess_artemis_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: GridScanParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.array(all_params["upper_left"])
        artemis_param_dict = extract_artemis_params_from_flat_dict(all_params)
        return ArtemisParameters(**artemis_param_dict)

    def get_scan_points(self, scan_number: int) -> dict:
        """Get the scan points for the first or second gridscan: scan number must be
        1 or 2"""
        if scan_number == 1:
            x_axis = self.experiment_params.x_axis
            y_axis = self.experiment_params.y_axis
            spec = Line(
                "sam_y",
                y_axis.start,
                y_axis.end,
                y_axis.full_steps,
            ) * ~Line(
                "sam_x",
                x_axis.start,
                x_axis.end,
                x_axis.full_steps,
            )
            scan_path = ScanPath(spec.calculate())
            return scan_path.consume().midpoints
        elif scan_number == 2:
            x_axis = self.experiment_params.x_axis
            z_axis = self.experiment_params.x_axis
            spec = Line(
                "sam_z",
                z_axis.start,
                z_axis.end,
                z_axis.full_steps,
            ) * ~Line(
                "sam_x",
                x_axis.start,
                x_axis.end,
                x_axis.full_steps,
            )
            scan_path = ScanPath(spec.calculate())
            return scan_path.consume().midpoints
        else:
            raise Exception("Cannot provide scan points for other scans than 1 or 2")

    def get_data_shape(self, scan_number: int):
        """Get the scan points for the first or second gridscan: scan number must be
        1 or 2"""
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        size = (
            self.artemis_params.detector_params.detector_size_constants.det_size_pixels
        )
        scan_points = self.get_scan_points(scan_number)
        ax = list(scan_points.keys())[0]
        num_frames_in_vds = len(scan_points[ax])
        return (num_frames_in_vds, size.width, size.height)

    def get_omega_start(self, scan_number: int) -> float:
        detector_params = self.artemis_params.detector_params
        if scan_number == 1:
            return detector_params.omega_start
        elif scan_number == 2:
            return detector_params.omega_start + 90
        else:
            raise Exception("Cannot provide parameters for other scans than 1 or 2")

    def get_run_number(self, scan_number: int) -> int:
        detector_params = self.artemis_params.detector_params
        if scan_number == 1:
            return detector_params.run_number
        elif scan_number == 2:
            return detector_params.run_number + 1
        else:
            raise Exception("Cannot provide parameters for other scans than 1 or 2")

    def get_filename(self, scan_number: int) -> str:
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        return f"{self.artemis_params.detector_params.prefix}_{self.get_run_number(scan_number)}"

    def get_nexus_info(self, scan_number: int) -> dict:
        """Returns a dict of info necessary for initialising NexusWriter, containing:
        data_shape, scan_points, omega_start, filename
        """
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        return {
            "data_shape": self.get_data_shape(scan_number),
            "scan_points": self.get_scan_points(scan_number),
            "omega_start": self.get_omega_start(scan_number),
            "filename": self.get_filename(scan_number),
        }
