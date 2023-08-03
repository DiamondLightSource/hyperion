from __future__ import annotations

from typing import Any, Optional

import numpy as np
from dodal.devices.detector import TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass

from artemis.external_interaction.ispyb.ispyb_dataclass import GridscanIspybParams
from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    extract_experiment_params_from_flat_dict,
)
from artemis.parameters.plan_specific.fgs_internal_params import (
    GridscanArtemisParameters,
)


@dataclass
class PinCentreThenXrayCentreParams(AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a plan that does a pin centre then xray centre
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance: float
    omega_start: float

    tip_offset_microns: Optional[float]
    grid_width_microns: Optional[float]

    def get_num_images(self):
        return 0


class PinCentreThenXrayCentreInternalParameters(InternalParameters):
    experiment_params: PinCentreThenXrayCentreParams
    artemis_params: GridscanArtemisParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **ArtemisParameters.Config.json_encoders,
        }

    def __init__(self, **args):
        super().__init__(**args)

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
        return PinCentreThenXrayCentreParams(
            **extract_experiment_params_from_flat_dict(
                PinCentreThenXrayCentreParams, experiment_params
            )
        )

    @validator("artemis_params", pre=True)
    def _preprocess_artemis_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: PinCentreThenXrayCentreParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.array([0, 0, 0])
        return GridscanArtemisParameters(
            **extract_artemis_params_from_flat_dict(
                all_params, cls._artemis_param_key_definitions()
            )
        )

    def get_data_shape(self):
        raise Exception("Data shape does not apply to this type of experiment!")

    def get_scan_points(cls):
        raise Exception("Scan points do not apply to this type of experiment!")
