from typing import Any, Dict

from dodal.devices.eiger import DetectorParams

import artemis.experiment_plans.experiment_registry as registry
from artemis.external_interaction.ispyb.ispyb_dataclass import (
    ISPYB_PARAM_DEFAULTS,
    IspybParams,
)
from artemis.parameters.constants import (
    DETECTOR_PARAM_DEFAULTS,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
    SIM_ZOCALO_ENV,
)
from artemis.parameters.external_parameters import RawParameters


class ArtemisParameters:
    zocalo_environment: str = SIM_ZOCALO_ENV
    beamline: str = SIM_BEAMLINE
    insertion_prefix: str = SIM_INSERTION_PREFIX
    experiment_type: str = registry.EXPERIMENT_NAMES[0]
    detector_params: Dict[str, Any] = DETECTOR_PARAM_DEFAULTS

    ispyb_params: Dict[str, Any] = ISPYB_PARAM_DEFAULTS

    def __init__(
        self,
        zocalo_environment: str = SIM_ZOCALO_ENV,
        beamline: str = SIM_BEAMLINE,
        insertion_prefix: str = SIM_INSERTION_PREFIX,
        experiment_type: str = registry.EXPERIMENT_NAMES[0],
        detector_params: Dict[str, Any] = DETECTOR_PARAM_DEFAULTS,
        ispyb_params: Dict[str, Any] = ISPYB_PARAM_DEFAULTS,
    ) -> None:
        self.zocalo_environment = zocalo_environment
        self.beamline = beamline
        self.insertion_prefix = insertion_prefix
        self.experiment_type = experiment_type
        self.detector_params = DetectorParams.from_dict(detector_params)
        self.ispyb_params = IspybParams.from_dict(ispyb_params)

    def __repr__(self):
        r = "artemis_params:\n"
        r += f"    zocalo_environment: {self.zocalo_environment}\n"
        r += f"    beamline: {self.beamline}\n"
        r += f"    insertion_prefix: {self.insertion_prefix}\n"
        r += f"    experiment_type: {self.experiment_type}\n"
        r += f"    detector_params: {self.detector_params}\n"
        r += f"    ispyb_params: {self.ispyb_params}\n"
        return r

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


class InternalParameters:
    artemis_params: ArtemisParameters
    experiment_params: registry.EXPERIMENT_TYPES

    def __init__(self, external_params: RawParameters = RawParameters()):
        self.artemis_params = ArtemisParameters(
            **external_params.artemis_params.to_dict()
        )
        self.experiment_params = registry.EXPERIMENT_TYPE_DICT[
            ArtemisParameters.experiment_type
        ](**external_params.experiment_params.to_dict())

    def __repr__(self):
        r = "[Artemis internal parameters]\n"
        r += repr(self.artemis_params)
        r += f"experiment_params: {self.experiment_params}"
        return r

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
        return cls(RawParameters.from_json(json_data))

    @classmethod
    def from_external_dict(cls, dict_data):
        """Convenience method to generate from external parameter dictionary, uses
        RawParameters.from_dict()"""
        return cls(RawParameters.from_dict(dict_data))
