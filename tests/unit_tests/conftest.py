from __future__ import annotations

from hyperion.parameters.external_parameters import from_json


def from_file(
    json_filename: str = "tests/test_data/parameter_json_files/test_parameter_defaults.json",
):
    with open(json_filename) as f:
        return from_json(f.read())
