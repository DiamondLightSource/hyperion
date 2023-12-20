from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    RobotLoadIspybParams,
)
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_experiment_params_from_flat_dict,
    extract_hyperion_params_from_flat_dict,
)


class WaitForRobotLoadThenCentreHyperionParameters(HyperionParameters):
    ispyb_params: RobotLoadIspybParams = RobotLoadIspybParams(
        **GRIDSCAN_ISPYB_PARAM_DEFAULTS
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **RobotLoadIspybParams.Config.json_encoders,
        }


@dataclass
class WaitForRobotLoadThenCentreParams(AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a plan that waits for robot load then does a
    centre.
    """

    exposure_time: float
    detector_distance: float
    omega_start: float
    snapshot_dir: str
    requested_energy_kev: float

    def get_num_images(self):
        return 0


class WaitForRobotLoadThenCentreInternalParameters(InternalParameters):
    experiment_params: WaitForRobotLoadThenCentreParams
    hyperion_params: WaitForRobotLoadThenCentreHyperionParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **HyperionParameters.Config.json_encoders,
        }

    @staticmethod
    def _hyperion_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        (
            hyperion_param_field_keys,
            detector_field_keys,
            ispyb_field_keys,
        ) = InternalParameters._hyperion_param_key_definitions()
        ispyb_field_keys += list(RobotLoadIspybParams.__annotations__.keys())
        return hyperion_param_field_keys, detector_field_keys, ispyb_field_keys

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        return WaitForRobotLoadThenCentreParams(
            **extract_experiment_params_from_flat_dict(
                WaitForRobotLoadThenCentreParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: WaitForRobotLoadThenCentreParams = values[
            "experiment_params"
        ]
        all_params["num_images"] = 0
        all_params["exposure_time"] = experiment_params.exposure_time
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.zeros(3, dtype=np.int32)
        return WaitForRobotLoadThenCentreHyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                all_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_data_shape(self):
        raise TypeError("Data shape does not apply to this type of experiment!")

    def get_scan_points(self):
        raise TypeError("Scan points do not apply to this type of experiment!")
