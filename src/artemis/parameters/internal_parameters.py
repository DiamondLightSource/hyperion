import copy

from artemis.parameters.constants import EXPERIMENT_TYPES
from artemis.parameters.external_parameters import ArtemisParameters, RawParameters


class InternalParameters:
    artemis_params: ArtemisParameters
    experiment_params: EXPERIMENT_TYPES

    def __init__(self, external_params: RawParameters = RawParameters()):
        self.artemis_params: ArtemisParameters = copy.deepcopy(
            external_params.artemis_params
        )
        self.experiment_params: EXPERIMENT_TYPES = copy.deepcopy(
            external_params.experiment_params
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
    def from_json(cls, json_data):
        """Convenience method to generate from external parameter JSON blob, uses
        RawParameters.from_json()"""
        return cls(RawParameters.from_json(json_data))
