from __future__ import annotations

import json
from os.path import join
from pathlib import Path
from typing import Any

import jsonschema

from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST


def validate_raw_parameters_from_dict(dict_params: dict[str, Any]) -> dict[str, Any]:
    with open(
        join(CONST.PARAMETER_SCHEMA_DIRECTORY, "full_external_parameters_schema.json"),
        "r",
    ) as f:
        full_schema = json.load(f)

    path = Path(CONST.PARAMETER_SCHEMA_DIRECTORY).absolute()
    resolver = jsonschema.validators.RefResolver(  # type: ignore # will be removed in param refactor
        base_uri=f"{path.as_uri()}/",
        referrer=True,
    )
    LOGGER.debug(f"Raw JSON recieved: {dict_params}")
    jsonschema.validate(dict_params, full_schema, resolver=resolver)
    return dict_params


def from_json(json_params: str):
    dict_params = json.loads(json_params)
    return validate_raw_parameters_from_dict(dict_params)
