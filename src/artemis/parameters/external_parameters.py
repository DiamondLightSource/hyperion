from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


def validate_raw_parameters_from_dict(dict_params: dict[str, Any]):
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
    return dict_params


def from_json(json_params: str):
    dict_params = json.loads(json_params)
    return validate_raw_parameters_from_dict(dict_params)


def from_file(json_filename: str):
    with open(json_filename) as f:
        return from_json(f.read())
