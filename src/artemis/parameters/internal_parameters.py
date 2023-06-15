from abc import abstractmethod
from typing import Any

from dodal.devices.eiger import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase
from pydantic import BaseModel, root_validator
from semver import Version

from artemis.parameters.constants import (
    DEFAULT_EXPERIMENT_TYPE,
    DETECTOR_PARAM_DEFAULTS,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.parameters.external_parameters import from_json


class ParameterVersion(Version):
    @classmethod
    def _parse(cls, version):
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls):
        """Return a list of validator methods for pydantic models."""
        yield cls._parse

    @classmethod
    def __modify_schema__(cls, field_schema):
        """Inject/mutate the pydantic field schema in-place."""
        field_schema.update(examples=["1.0.2", "2.15.3-alpha", "21.3.15-beta+12345"])


class ArtemisParameters(BaseModel):
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = DEFAULT_EXPERIMENT_TYPE
    detector_params: DetectorParams = DetectorParams(**DETECTOR_PARAM_DEFAULTS)


def flatten_dict(d: dict, parent_items: dict = {}) -> dict:
    """Flatten a dictionary assuming all keys are unique."""
    items: dict = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flattened_subdict = flatten_dict(v, items)
            items.update(flattened_subdict)
        else:
            if (
                k in items
                or k in parent_items
                and (items.get(k) or parent_items.get(k)) != v
            ):
                raise Exception(
                    f"Duplicate keys '{k}' in input parameters with differing values "
                    f"'{v}' and '{(items.get(k) or parent_items.get(k))}'!"
                )
            items[k] = v
    return items


def fetch_subdict_from_bucket(
    list_of_keys: list[str], bucket: dict[str, Any]
) -> dict[str, Any]:
    return {key: bucket.get(key) for key in list_of_keys if bucket.get(key) is not None}


def extract_experiment_params_from_flat_dict(
    experiment_param_class, flat_params: dict[str, Any]
):
    experiment_field_keys = list(experiment_param_class.__annotations__.keys())
    experiment_params_args = fetch_subdict_from_bucket(
        experiment_field_keys, flat_params
    )
    return experiment_params_args


def get_extracted_experiment_and_flat_artemis_params(
    experiment_param_class, flat_params: dict[str, Any]
):
    return {
        "experiment_params": extract_experiment_params_from_flat_dict(
            experiment_param_class, flat_params
        ),
        "artemis_params": flat_params,
    }


def extract_artemis_params_from_flat_dict(
    external_params: dict[str, Any],
    artemis_param_key_definitions: tuple[list[str], list[str], list[str]],
) -> dict[str, Any]:
    all_params_bucket = flatten_dict(external_params)

    (
        artemis_param_field_keys,
        detector_field_keys,
        ispyb_field_keys,
    ) = artemis_param_key_definitions

    artemis_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        artemis_param_field_keys, all_params_bucket
    )
    detector_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        detector_field_keys, all_params_bucket
    )
    ispyb_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        ispyb_field_keys, all_params_bucket
    )
    artemis_params_args["ispyb_params"] = ispyb_params_args
    artemis_params_args["detector_params"] = detector_params_args

    return artemis_params_args


class InternalParameters(BaseModel):
    params_version: ParameterVersion
    experiment_params: AbstractExperimentParameterBase
    artemis_params: ArtemisParameters

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {
            ParameterVersion: lambda pv: str(pv),
        }

    @classmethod
    def from_json(cls, data):
        return cls(**(from_json(data)))

    @root_validator(pre=True)
    def _preprocess_all(cls, values):
        values["artemis_params"] = flatten_dict(values)
        return values

    @staticmethod
    @abstractmethod
    def _artemis_param_key_definitions():
        ...

    @abstractmethod
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        ...

    @abstractmethod
    def _preprocess_artemis_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        ...
