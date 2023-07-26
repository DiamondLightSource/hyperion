from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.devices.fast_grid_scan import GridAxis, GridScanParams
from pydantic import validator
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
)
from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


class GridscanArtemisParameters(ArtemisParameters):
    ispyb_params: GridscanIspybParams = GridscanIspybParams(
        **GRIDSCAN_ISPYB_PARAM_DEFAULTS
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **GridscanIspybParams.Config.json_encoders,
        }


class FGSInternalParameters(InternalParameters):
    experiment_params: GridScanParams
    artemis_params: GridscanArtemisParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **GridscanArtemisParameters.Config.json_encoders,
        }

    @staticmethod
    def _artemis_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        (
            artemis_param_field_keys,
            detector_field_keys,
            ispyb_field_keys,
        ) = InternalParameters._artemis_param_key_definitions()
        ispyb_field_keys += list(GridscanIspybParams.__annotations__.keys())
        return artemis_param_field_keys, detector_field_keys, ispyb_field_keys

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
        artemis_param_dict = extract_artemis_params_from_flat_dict(
            all_params, cls._artemis_param_key_definitions()
        )
        return GridscanArtemisParameters(**artemis_param_dict)

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
        size = (
            self.artemis_params.detector_params.detector_size_constants.det_size_pixels
        )
        ax = list(scan_points.keys())[0]
        num_frames_in_vds = len(scan_points[ax])
        return (num_frames_in_vds, size.width, size.height)

    def get_omega_start(self, scan_number: int) -> float:
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        detector_params = self.artemis_params.detector_params
        return detector_params.omega_start + 90 * (scan_number - 1)

    def get_run_number(self, scan_number: int) -> int:
        assert (
            scan_number == 1 or scan_number == 2
        ), "Cannot provide parameters for other scans than 1 or 2"
        detector_params = self.artemis_params.detector_params
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
