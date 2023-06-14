from __future__ import annotations

from typing import Any

import numpy as np
from dataclasses_json import DataClassJsonMixin
from dodal.devices.detector import TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass

from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)


@dataclass
class GridScanWithEdgeDetectParams(DataClassJsonMixin, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a grid scan that uses edge detection to detect the grid.
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance: float
    omega_start: float

    def get_num_images(self):
        return 0


class GridScanWithEdgeDetectInternalParameters(InternalParameters):
    experiment_params: GridScanWithEdgeDetectParams
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
        return GridScanWithEdgeDetectParams(
            **extract_experiment_params_from_flat_dict(
                GridScanWithEdgeDetectParams, experiment_params
            )
        )

    @validator("artemis_params", pre=True)
    def _preprocess_artemis_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: GridScanWithEdgeDetectParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.array([0, 0, 0])
        return ArtemisParameters(**extract_artemis_params_from_flat_dict(all_params))
