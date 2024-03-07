from __future__ import annotations

import json
from os.path import join
from pathlib import Path
from typing import Any

import jsonschema

from hyperion.log import LOGGER
from hyperion.parameters.constants import PARAMETER_SCHEMA_DIRECTORY


def validate_raw_parameters_from_dict(dict_params: dict[str, Any]) -> dict[str, Any]:
    with open(
        join(PARAMETER_SCHEMA_DIRECTORY, "full_external_parameters_schema.json"), "r"
    ) as f:
        full_schema = json.load(f)

    path = Path(PARAMETER_SCHEMA_DIRECTORY).absolute()
    resolver = jsonschema.validators.RefResolver(
        base_uri=f"{path.as_uri()}/",
        referrer=True,
    )
    LOGGER.debug(f"Raw JSON recieved: {dict_params}")
    jsonschema.validate(dict_params, full_schema, resolver=resolver)
    return dict_params


def from_json(json_params: str):
    dict_params = json.loads(json_params)
    return validate_raw_parameters_from_dict(dict_params)


def from_file(
    json_filename: str = "tests/test_data/parameter_json_files/test_parameter_defaults.json",
):
    with open(json_filename) as f:
        return from_json(f.read())
