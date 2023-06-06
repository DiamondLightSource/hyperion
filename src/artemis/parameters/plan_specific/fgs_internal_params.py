from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.devices.fast_grid_scan import GridScanParams
from pydantic import validator

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
    IspybParams,
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # TODO REMOVE JUST FOR DEBUGGING

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
            **GridScanParams.Config.json_encoders,
            **GridscanArtemisParameters.Config.json_encoders,
        }

    @staticmethod
    def _artemis_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        artemis_param_field_keys = [
            "zocalo_environment",
            "beamline",
            "insertion_prefix",
            "experiment_type",
        ]
        detector_field_keys = list(DetectorParams.__annotations__.keys())
        # not an annotation but specified as field encoder in DetectorParams:
        detector_field_keys.append("detector")
        ispyb_field_keys = list(IspybParams.__annotations__.keys()) + list(
            GridscanIspybParams.__annotations__.keys()
        )

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
