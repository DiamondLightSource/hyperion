import json
from pathlib import Path

import jsonschema
import pytest
from dodal.devices.fast_grid_scan import GridScanParams
from jsonschema import ValidationError

schema_folder = "src/hyperion/parameters/schemas/"
with open(schema_folder + "full_external_parameters_schema.json", "r") as f:
    full_schema = json.load(f)
with open(schema_folder + "hyperion_parameters_schema.json", "r") as f:
    hyperion_schema = json.load(f)
with open(schema_folder + "detector_parameters_schema.json", "r") as f:
    detector_schema = json.load(f)
with open(schema_folder + "ispyb_parameters_schema.json", "r") as f:
    ispyb_schema = json.load(f)
with open(
    schema_folder + "experiment_schemas/grid_scan_params_schema.json",
    "r",
) as f:
    grid_scan_schema = json.load(f)
with open(
    schema_folder + "experiment_schemas/rotation_scan_params_schema.json",
    "r",
) as f:
    rotation_scan_schema = json.load(f)
with open(
    "tests/test_data/parameter_json_files/good_test_parameters.json",
    "r",
) as f:
    params = json.load(f)

path = Path(schema_folder + "").absolute()
resolver = jsonschema.validators.RefResolver(
    base_uri=f"{path.as_uri()}/",
    referrer=True,
)


def test_good_params_validates():
    jsonschema.validate(params, full_schema, resolver=resolver)


def test_good_params_hyperionparams_validates():
    jsonschema.validate(params["hyperion_params"], hyperion_schema, resolver=resolver)


def test_good_params_GridscanIspybParams_validates():
    jsonschema.validate(
        params["hyperion_params"]["ispyb_params"], ispyb_schema, resolver=resolver
    )


def test_good_params_detectorparams_validates():
    jsonschema.validate(
        params["hyperion_params"]["detector_params"], detector_schema, resolver=resolver
    )


def test_good_params_gridparams_validates():
    jsonschema.validate(
        params["experiment_params"], grid_scan_schema, resolver=resolver
    )


def test_serialised_grid_scan_params_validate():
    params = GridScanParams(transmission_fraction=0.01)
    json_params = params.json()
    jsonschema.validate(json.loads(json_params), grid_scan_schema, resolver=resolver)


def test_good_params_rotationparams_validates():
    with open(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json",
        "r",
    ) as f:
        params = json.load(f)
    jsonschema.validate(
        params["experiment_params"], rotation_scan_schema, resolver=resolver
    )


def test_bad_params_wrong_version_raises_exception():
    with open(
        "tests/test_data/parameter_json_files/bad_test_parameters_wrong_version.json",
        "r",
    ) as f:
        params = json.load(f)
    with pytest.raises(ValidationError):
        jsonschema.validate(params, full_schema, resolver=resolver)
