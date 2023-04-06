from abc import ABC, abstractmethod
from typing import Any, Dict

from dodal.devices.eiger import DetectorParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

import artemis.parameters.external_parameters as raw_parameters
from artemis.external_interaction.ispyb.ispyb_dataclass import (
    ISPYB_PARAM_DEFAULTS,
    IspybParams,
)
from artemis.parameters.constants import (
    DEFAULT_EXPERIMENT_TYPE,
    DETECTOR_PARAM_DEFAULTS,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.utils import Point3D


class ArtemisParameters:
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = DEFAULT_EXPERIMENT_TYPE

    detector_params: DetectorParams = DetectorParams.from_dict(DETECTOR_PARAM_DEFAULTS)
    ispyb_params: IspybParams = IspybParams.from_dict(ISPYB_PARAM_DEFAULTS)

    def __init__(
        self,
        zocalo_environment: str = SIM_ZOCALO_ENV,
        beamline: str = SIM_BEAMLINE,
        insertion_prefix: str = SIM_INSERTION_PREFIX,
        experiment_type: str = DEFAULT_EXPERIMENT_TYPE,
        detector_params: Dict[str, Any] = DETECTOR_PARAM_DEFAULTS,
        ispyb_params: Dict[str, Any] = ISPYB_PARAM_DEFAULTS,
    ) -> None:
        self.zocalo_environment = zocalo_environment
        self.beamline = beamline
        self.insertion_prefix = insertion_prefix
        self.experiment_type = experiment_type
        self.detector_params: DetectorParams = DetectorParams.from_dict(detector_params)
        self.ispyb_params: IspybParams = IspybParams.from_dict(ispyb_params)

    def __repr__(self):
        return (
            "artemis_params:\n"
            f"    zocalo_environment: {self.zocalo_environment}\n"
            f"    beamline: {self.beamline}\n"
            f"    insertion_prefix: {self.insertion_prefix}\n"
            f"    experiment_type: {self.experiment_type}\n"
            f"    detector_params: {self.detector_params}\n"
            f"    ispyb_params: {self.ispyb_params}\n"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, ArtemisParameters):
            return NotImplemented
        elif self.zocalo_environment != other.zocalo_environment:
            return False
        elif self.beamline != other.beamline:
            return False
        elif self.insertion_prefix != other.insertion_prefix:
            return False
        elif self.experiment_type != other.experiment_type:
            return False
        elif self.detector_params != other.detector_params:
            return False
        elif self.ispyb_params != other.ispyb_params:
            return False
        return True


def flatten_dict(d: dict, parent_items: dict = {}) -> dict:
    """Flatten a dictionary assuming all keys are unique."""
    items: dict = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flattened_subdict = flatten_dict(v, items)
            items.update(flattened_subdict)
        else:
            if k in items or k in parent_items:
                raise Exception(f"Duplicate keys '{k}' in input parameters!")
            items[k] = v
    return items


class InternalParameters(ABC):
    """A base class with some helpful functions to aid in conversion from external
    json parameters to internal experiment parameter classes, DetectorParams,
    IspybParams, etc.
    When subclassing you must provide the experiment parameter type as the
    'experiment_params_type' property, which must be a subclass of
    dodal.parameters.experiment_parameter_base.AbstractExperimentParameterBase.
    The corresponding initialisation values must be present in the external parameters
    and be validated by the json schema.
    Override or extend pre_sorting_translation() to modify key names or values before
    sorting, and key_definitions() to determine which keys to send to DetectorParams and
    IspybParams."""

    artemis_params: ArtemisParameters

    def __init__(self, external_params: dict = raw_parameters.from_file()):
        all_params_bucket = flatten_dict(external_params)
        self.experiment_param_preprocessing(all_params_bucket)

        experiment_field_keys = list(self.experiment_params_type.__annotations__.keys())
        experiment_field_args: dict[str, Any] = {
            key: all_params_bucket.get(key)
            for key in experiment_field_keys
            if all_params_bucket.get(key) is not None
        }
        self.experiment_params: AbstractExperimentParameterBase = (
            self.experiment_params_type(**experiment_field_args)
        )

        self.artemis_param_preprocessing(all_params_bucket)
        (
            artemis_param_field_keys,
            detector_field_keys,
            ispyb_field_keys,
        ) = self.key_definitions()

        artemis_params_args: dict[str, Any] = {
            key: all_params_bucket.get(key)
            for key in artemis_param_field_keys
            if all_params_bucket.get(key) is not None
        }
        detector_params_args = {
            key: all_params_bucket.get(key)
            for key in detector_field_keys
            if all_params_bucket.get(key) is not None
        }
        ispyb_params_args = {
            key: all_params_bucket.get(key)
            for key in ispyb_field_keys
            if all_params_bucket.get(key) is not None
        }
        artemis_params_args["ispyb_params"] = ispyb_params_args
        artemis_params_args["detector_params"] = detector_params_args

        self.artemis_params = ArtemisParameters(**artemis_params_args)

    @property
    @abstractmethod
    def experiment_params_type(self):
        """This should be set to the experiment param type"""
        pass

    def key_definitions(self):
        artemis_param_field_keys = [
            "zocalo_environment",
            "beamline",
            "insertion_prefix",
            "experiment_type",
        ]
        detector_field_keys = list(DetectorParams.__annotations__.keys())
        # not an annotation but specified as field encoder in DetectorParams:
        detector_field_keys.append("detector")
        ispyb_field_keys = list(IspybParams.__annotations__.keys())

        return artemis_param_field_keys, detector_field_keys, ispyb_field_keys

    def experiment_param_preprocessing(self, param_dict: dict[str, Any]):
        """operates on the supplied experiment parameter values befause the experiment
        parameters object is initialised."""
        pass

    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        """Operates on the the flattened external param dictionary before its values are
        distributed to the other dictionaries. In the default implementation,
        self.experiment_params is already initialised, so values which are defined or
        calculated there (e.g. num_images) are available.
        Subclasses should extend or override this to define translations of names in the
        external parameter set, applied to the param_dict. For example, in rotation
        scans, `omega_increment` (for the detector) needs to come from the externally
        supplied `rotation_increment` if the axis is omega.
        """

        param_dict["num_images"] = self.experiment_params.get_num_images()
        param_dict["upper_left"] = Point3D(*param_dict["upper_left"])
        param_dict["position"] = Point3D(*param_dict["position"])

    def __repr__(self):
        return (
            "[Artemis internal parameters]\n"
            f"{self.artemis_params}"
            f"experiment_params: {self.experiment_params}"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, InternalParameters):
            return NotImplemented
        if self.artemis_params != other.artemis_params:
            return False
        if self.experiment_params != other.experiment_params:
            return False
        return True

    @classmethod
    def from_external_json(cls, json_data):
        """Convenience method to generate from external parameter JSON blob, uses
        RawParameters.from_json()"""
        return cls(raw_parameters.from_json(json_data))

    @classmethod
    def from_external_dict(cls, dict_data):
        """Convenience method to generate from external parameter dictionary, uses
        RawParameters.from_dict()"""
        return cls(raw_parameters.validate_raw_parameters_from_dict(dict_data))
