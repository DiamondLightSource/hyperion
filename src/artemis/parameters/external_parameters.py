import copy
import json
from pathlib import Path

import jsonschema

from artemis.parameters.constants import EXPERIMENT_DICT, EXPERIMENT_TYPES


class WrongExperimentParameterSpecification(Exception):
    pass


class RawParameters:
    params: dict

    def __init__(self, params) -> None:
        self.params = copy.deepcopy(params)

    def __eq__(self, other) -> bool:
        if not isinstance(other, RawParameters):
            return NotImplemented
        if self.params != other.params:
            return False
        return True

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
