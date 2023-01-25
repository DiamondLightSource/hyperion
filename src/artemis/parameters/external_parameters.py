import copy
import json
from dataclasses import dataclass, field
from os import environ
from pathlib import Path

import jsonschema

from artemis.parameters.constants import (
    EXPERIMENT_DICT,
    EXPERIMENT_TYPES,
    SIM_BEAMLINE,
    SIM_INSERTION_PREFIX,
)


class WrongExperimentParameterSpecification(Exception):
    pass


@dataclass
class BeamlinePrefixes:
    beamline_prefix: str
    insertion_prefix: str


def get_beamline_prefixes():
    beamline = environ.get("BEAMLINE")
    if beamline is None:
        return BeamlinePrefixes(SIM_BEAMLINE, SIM_INSERTION_PREFIX)
    if beamline == "i03":
        return BeamlinePrefixes("BL03I", "SR03I")


def default_field(obj):
    return field(default_factory=lambda: copy.deepcopy(obj))


class RawParameters:
    params: dict

    def __init__(self, params=None) -> None:
        if params is None:
            self.params = self.from_file(
                "src/artemis/parameters/tests/test_data/good_test_parameters_minimal.json"
            ).params
        else:
            self.params = copy.deepcopy(params)

    def __eq__(self, other) -> bool:
        if not isinstance(other, RawParameters):
            return NotImplemented
        if self.params != other.params:
            return False
        return True

    def __getitem__(self, item):
        return self.params.get(item)

    def to_dict(self) -> dict[str, dict]:
        return self.params

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, dict_params: dict[str, dict]):
        with open(
            "src/artemis/parameters/schemas/full_external_parameters_schema.json", "r"
        ) as f:
            full_schema = json.load(f)

        path = Path("src/artemis/parameters/schemas/").absolute()
        resolver = jsonschema.validators.RefResolver(
            base_uri=f"{path.as_uri()}/",
            referrer=True,
        )
        # TODO improve failed validation error messages
        jsonschema.validate(dict_params, full_schema, resolver=resolver)
        experiment_type: EXPERIMENT_TYPES = EXPERIMENT_DICT.get(
            dict_params["artemis_params"]["experiment_type"]
        )
        try:
            assert experiment_type is not None
        except Exception:
            raise WrongExperimentParameterSpecification(
                "Either the experiment type parameter does not match a known experiment"
                "type, or the experiment parameters were not correct."
            )
        return cls(dict_params)

    @classmethod
    def from_json(cls, json_params: str):
        dict_params = json.loads(json_params)
        return cls.from_dict(dict_params)

    @classmethod
    def from_file(cls, json_filename: str):
        with open(json_filename) as f:
            return cls.from_json(f.read())
