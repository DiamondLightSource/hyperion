from typing import Any

from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import validator
from pydantic.dataclasses import dataclass

from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_experiment_params_from_flat_dict,
    extract_hyperion_params_from_flat_dict,
)


class SetEnergyHyperionParameters(HyperionParameters):
    pass


@dataclass
class SetEnergyParams(AbstractExperimentParameterBase):
    requested_energy_kev: float

    def get_num_images(self):
        return 0


class SetEnergyInternalParameters(InternalParameters):
    experiment_params: SetEnergyParams
    hyperion_params: SetEnergyHyperionParameters

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(cls, experiment_params: dict[str, Any]):
        return SetEnergyParams(
            **extract_experiment_params_from_flat_dict(
                SetEnergyParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        tmp_params = all_params | {
            "num_triggers": 0,
            "num_images_per_trigger": 0,
            "omega_increment": 0,
            "omega_start": 0,
            "detector_distance": 0,
            "exposure_time": 0,
        }
        return HyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                tmp_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_scan_points(cls) -> dict[str, list]:
        raise TypeError("Set Energy does not support scan points")

    def get_data_shape(cls) -> tuple[int, int, int]:
        raise TypeError("Set Energy does not support data shape")
