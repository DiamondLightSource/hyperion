from abc import abstractmethod
from typing import Any

from dodal.devices.eiger import DetectorParams
from dodal.utils import BeamlinePrefix, get_beamline_name
from pydantic import BaseModel, root_validator

from hyperion.experiment_plans.experiment_registry import PLAN_REGISTRY
from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.parameters.external_parameters import ExternalParameters, ParameterVersion
from hyperion.parameters.jsonschema_external_parameters import from_json


class HyperionParameters(BaseModel):
    zocalo_environment: str
    beamline: str
    insertion_prefix: str
    experiment_type: str
    detector_params: DetectorParams
    ispyb_params: IspybParams

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **DetectorParams.Config.json_encoders,
            **IspybParams.Config.json_encoders,
        }

    @classmethod
    def from_external(cls, external: ExternalParameters):
        assert (
            external._experiment_type is not None
        ), "Can't initialise HyperionParameters from ExternalParameters without set '_experiment_type' field."
        ispyb_param_type = PLAN_REGISTRY[external._experiment_type]["ispyb_param_type"]
        return cls(
            zocalo_environment=external.data_parameters.zocalo_environment
            or "artemis-dev",
            beamline=external.data_parameters.beamline or get_beamline_name("i03"),
            insertion_prefix=external.data_parameters.insertion_prefix
            or BeamlinePrefix(get_beamline_name("i03")).insertion_prefix,
            experiment_type=external._experiment_type,
            detector_params=DetectorParams(
                **external.data_parameters.dict(),
                **external.experiment_parameters.dict(),
            ),
            ispyb_params=ispyb_param_type.from_external(external),
        )


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


def get_extracted_experiment_and_flat_hyperion_params(
    experiment_param_class, flat_params: dict[str, Any]
):
    return {
        "experiment_params": extract_experiment_params_from_flat_dict(
            experiment_param_class, flat_params
        ),
        "hyperion_params": flat_params,
    }


def extract_hyperion_params_from_flat_dict(
    external_params: dict[str, Any],
    hyperion_param_key_definitions: tuple[list[str], list[str], list[str]],
) -> dict[str, Any]:
    all_params_bucket = flatten_dict(external_params)

    (
        hyperion_param_field_keys,
        detector_field_keys,
        ispyb_field_keys,
    ) = hyperion_param_key_definitions

    hyperion_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        hyperion_param_field_keys, all_params_bucket
    )
    detector_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        detector_field_keys, all_params_bucket
    )
    ispyb_params_args: dict[str, Any] = fetch_subdict_from_bucket(
        ispyb_field_keys, all_params_bucket
    )
    hyperion_params_args["ispyb_params"] = ispyb_params_args
    hyperion_params_args["detector_params"] = detector_params_args

    return hyperion_params_args


class InternalParameters(BaseModel):
    params_version: ParameterVersion

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
        values["hyperion_params"] = flatten_dict(values)
        return values

    @staticmethod
    def _hyperion_param_key_definitions():
        hyperion_param_field_keys = [
            "zocalo_environment",
            "beamline",
            "insertion_prefix",
            "experiment_type",
        ]
        detector_field_keys = list(DetectorParams.__annotations__.keys())
        # not an annotation but specified as field encoder in DetectorParams:
        detector_field_keys.append("detector")
        ispyb_field_keys = list(IspybParams.__annotations__.keys())
        return hyperion_param_field_keys, detector_field_keys, ispyb_field_keys

    @abstractmethod
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        ...

    @abstractmethod
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        ...

    @abstractmethod
    def get_scan_points(cls) -> dict[str, list]:
        """Get points of the scan as calculated by scanspec."""
        ...

    @abstractmethod
    def get_data_shape(cls) -> tuple[int, int, int]:
        """Get the shape of the data resulting from the experiment specified by
        these parameters."""
        ...
