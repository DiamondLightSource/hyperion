from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import TriggerMode
from dodal.devices.fast_grid_scan import GridScanParams
from pydantic import validator

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
