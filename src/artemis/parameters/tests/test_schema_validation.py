import json
from pathlib import Path

import jsonschema
import pytest
from dodal.devices.fast_grid_scan import GridScanParams
from jsonschema import ValidationError

schema_folder = "src/artemis/parameters/schemas/"
with open(schema_folder + "full_external_parameters_schema.json", "r") as f:
    full_schema = json.load(f)
with open(schema_folder + "artemis_parameters_schema.json", "r") as f:
    artemis_schema = json.load(f)
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
with open("src/artemis/parameters/tests/test_data/good_test_parameters.json", "r") as f:
    params = json.load(f)

path = Path(schema_folder + "").absolute()
resolver = jsonschema.validators.RefResolver(
    base_uri=f"{path.as_uri()}/",
    referrer=True,
)


def test_good_params_validates():
    jsonschema.validate(params, full_schema, resolver=resolver)


def test_good_params_artemisparams_validates():
    jsonschema.validate(params["artemis_params"], artemis_schema, resolver=resolver)


def test_good_params_ispybparams_validates():
    jsonschema.validate(
        params["artemis_params"]["ispyb_params"], ispyb_schema, resolver=resolver
    )


def test_good_params_detectorparams_validates():
    jsonschema.validate(
        params["artemis_params"]["detector_params"], detector_schema, resolver=resolver
    )


def test_good_params_gridparams_validates():
    jsonschema.validate(
        params["experiment_params"], grid_scan_schema, resolver=resolver
    )


def test_serialised_grid_scan_params_validate():
    from dodal.devices.fast_grid_scan import GridScanParams

    params = GridScanParams().json()
    jsonschema.validate(json.loads(params), grid_scan_schema, resolver=resolver)


def test_good_params_rotationparams_validates():
    with open(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json",
        "r",
    ) as f:
        params = json.load(f)
    jsonschema.validate(
        params["experiment_params"], rotation_scan_schema, resolver=resolver
    )


def test_bad_params_wrong_version_raises_exception():
    with open(
        "src/artemis/parameters/tests/test_data/bad_test_parameters_wrong_version.json",
        "r",
    ) as f:
        params = json.load(f)
    with pytest.raises(ValidationError):
        jsonschema.validate(params, full_schema, resolver=resolver)
