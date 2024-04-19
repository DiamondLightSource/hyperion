from __future__ import annotations

from typing import Any, Optional

import numpy as np
from dodal.devices.detector import DetectorParams, TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentWithBeamParams
from pydantic import validator

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    RobotLoadIspybParams,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_experiment_params_from_flat_dict,
    extract_hyperion_params_from_flat_dict,
)


class RobotLoadThenCentreHyperionParameters(HyperionParameters):
    ispyb_params: RobotLoadIspybParams = RobotLoadIspybParams(  # type: ignore
        **GRIDSCAN_ISPYB_PARAM_DEFAULTS
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **RobotLoadIspybParams.Config.json_encoders,
        }


class RobotLoadThenCentreParams(AbstractExperimentWithBeamParams):
    """
    Holder class for the parameters of a plan that waits for robot load then does a
    centre.
    """

    exposure_time: float
    detector_distance: float
    omega_start: float
    snapshot_dir: str

    sample_puck: int
    sample_pin: int

    requested_energy_kev: Optional[float] = None

    # Distance for the smargon to accelerate into the grid and decelerate out of the grid when using the panda
    run_up_distance_mm: float = CONST.HARDWARE.PANDA_FGS_RUN_UP_DEFAULT

    # Use constant motion panda scans instead of fast grid scans
    use_panda: bool = False

    def get_num_images(self):
        return 0


class RobotLoadThenCentreInternalParameters(InternalParameters):
    experiment_params: RobotLoadThenCentreParams
    hyperion_params: RobotLoadThenCentreHyperionParameters

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
        return RobotLoadThenCentreParams(
            **extract_experiment_params_from_flat_dict(
                RobotLoadThenCentreParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: RobotLoadThenCentreParams = values["experiment_params"]
        all_params["num_images"] = 0
        all_params["exposure_time"] = experiment_params.exposure_time
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.zeros(3, dtype=np.int32)
        all_params["expected_energy_ev"] = None
        return RobotLoadThenCentreHyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                all_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_data_shape(self):
        raise TypeError("Data shape does not apply to this type of experiment!")

    def get_scan_points(self):
        raise TypeError("Scan points do not apply to this type of experiment!")
