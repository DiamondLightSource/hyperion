import copy
import json

import numpy as np
import pytest
from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams
from pydantic import ValidationError

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
)
from hyperion.parameters import external_parameters
from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.internal_parameters import (
    InternalParameters,
    extract_hyperion_params_from_flat_dict,
    fetch_subdict_from_bucket,
    flatten_dict,
    get_extracted_experiment_and_flat_hyperion_params,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanHyperionParameters,
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def raw_params():
    return external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )


@pytest.fixture
def rotation_raw_params():
    return external_parameters.from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )


@pytest.fixture
def gridscan_params(raw_params):
    return GridscanInternalParameters(**raw_params)


@pytest.fixture
def rotation_params(rotation_raw_params):
    return RotationInternalParameters(**rotation_raw_params)


TEST_PARAM_DICT = {
    "layer_1": {
        "a": 23,
        "x": 56,
        "k": 47,
        "layer_2": {"l": 11, "h": "test_value"},
        "layer_3": {"b": 5, "c": 6, "y": 7, "z": "test_value_2"},
    }
}


def test_cant_initialise_abstract_internalparams():
    with pytest.raises(TypeError):
        internal_parameters = InternalParameters(  # noqa
            **external_parameters.from_file()
        )


def test_ispyb_param_wavelength():
    from hyperion.utils.utils import convert_eV_to_angstrom

    ispyb_params = GridscanIspybParams(**GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    assert ispyb_params.wavelength_angstroms == pytest.approx(
        convert_eV_to_angstrom(GRIDSCAN_ISPYB_PARAM_DEFAULTS["current_energy_ev"])
    )


def test_ispyb_param_dict():
    ispyb_params = GridscanIspybParams(**GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    as_dict = ispyb_params.dict()
    assert isinstance(as_dict.get("position"), list)
    modified_params = copy.deepcopy(GRIDSCAN_ISPYB_PARAM_DEFAULTS)
    modified_params["position"] = [123, 7777777, 3]
    modified_ispyb_params = GridscanIspybParams(**modified_params)
    assert ispyb_params != modified_ispyb_params
    assert isinstance(modified_ispyb_params.position, np.ndarray)
    modified_as_dict = modified_ispyb_params.dict()
    assert modified_as_dict.get("position") == [123, 7777777, 3]


def test_internal_param_serialisation_deserialisation():
    data = from_file()
    internal_parameters = GridscanInternalParameters(**data)

    serialised = internal_parameters.json(indent=2)
    reloaded = json.loads(serialised)

    deserialised = GridscanInternalParameters(**reloaded)

    assert deserialised == internal_parameters


def test_flatten():
    params = external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )
    flat_dict = flatten_dict(params)
    for k in flat_dict:
        assert not isinstance(flat_dict[k], dict)

    flat_test_dict = flatten_dict(TEST_PARAM_DICT)
    for k in ["a", "b", "c", "h", "k", "l", "x", "y", "z"]:
        assert k in flat_test_dict

    with pytest.raises(Exception):
        flatten_dict({"x": 6, "y": {"x": 7}})


def test_hyperion_params_needs_values_from_experiment(raw_params):
    extracted_hyperion_param_dict = extract_hyperion_params_from_flat_dict(
        flatten_dict(raw_params),
        GridscanInternalParameters._hyperion_param_key_definitions(),
    )
    with pytest.raises(ValidationError):
        hyperion_params = GridscanHyperionParameters(**extracted_hyperion_param_dict)
    with pytest.raises(UnboundLocalError):
        assert hyperion_params is not None


def test_hyperion_parameters_only_from_file():
    with open("tests/test_data/hyperion_parameters.json") as f:
        hyperion_param_dict = json.load(f)
    hyperion_params_deserialised = GridscanHyperionParameters(**hyperion_param_dict)
    ispyb = hyperion_params_deserialised.ispyb_params
    detector = hyperion_params_deserialised.detector_params
    assert isinstance(ispyb, GridscanIspybParams)
    assert isinstance(detector, DetectorParams)


def test_hyperion_params_can_be_deserialised_from_internal_representation(raw_params):
    internal_params = GridscanInternalParameters(**raw_params)
    hyperion_param_json = internal_params.hyperion_params.json()
    hyperion_param_dict = json.loads(hyperion_param_json)
    assert hyperion_param_dict.get("ispyb_params") is not None
    assert hyperion_param_dict.get("detector_params") is not None
    hyperion_params_deserialised = GridscanHyperionParameters(**hyperion_param_dict)
    assert internal_params.hyperion_params == hyperion_params_deserialised
    ispyb = hyperion_params_deserialised.ispyb_params
    detector = hyperion_params_deserialised.detector_params
    assert isinstance(ispyb, GridscanIspybParams)
    assert isinstance(detector, DetectorParams)


def test_hyperion_params_eq(raw_params):
    internal_params = GridscanInternalParameters(**raw_params)

    hyperion_params_1 = internal_params.hyperion_params
    hyperion_params_2 = copy.deepcopy(hyperion_params_1)
    assert hyperion_params_1 == hyperion_params_2

    hyperion_params_2.zocalo_environment = "some random thing"
    assert hyperion_params_1 != hyperion_params_2

    hyperion_params_2 = copy.deepcopy(hyperion_params_1)
    hyperion_params_2.insertion_prefix = "some random thing"
    assert hyperion_params_1 != hyperion_params_2

    hyperion_params_2 = copy.deepcopy(hyperion_params_1)
    hyperion_params_2.experiment_type = "some random thing"
    assert hyperion_params_1 != hyperion_params_2

    hyperion_params_2 = copy.deepcopy(hyperion_params_1)
    hyperion_params_2.detector_params.current_energy_ev = 99999
    assert hyperion_params_1 != hyperion_params_2

    hyperion_params_2 = copy.deepcopy(hyperion_params_1)
    hyperion_params_2.ispyb_params.beam_size_x = 99999
    assert hyperion_params_1 != hyperion_params_2


def test_get_extracted_experiment_and_flat_hyperion_params(raw_params):
    flat_params = flatten_dict(raw_params)
    processed_params = get_extracted_experiment_and_flat_hyperion_params(
        GridScanParams, flat_params
    )
    assert processed_params.get("experiment_params") not in [None, {}]
    experiment_params = GridScanParams(**processed_params.get("experiment_params"))
    assert experiment_params.x_steps == flat_params["x_steps"]
    assert experiment_params.y_steps == flat_params["y_steps"]
    assert experiment_params.z_steps == flat_params["z_steps"]


def test_fetch_subdict(raw_params):
    keys_all_in = ["x_steps", "y_steps", "z_steps"]
    keys_not_all_in = ["x_steps", "y_steps", "z_steps", "asdfghjk"]
    flat_params = flatten_dict(raw_params)
    subdict = fetch_subdict_from_bucket(keys_all_in, flat_params)
    assert len(subdict) == 3
    subdict_2 = fetch_subdict_from_bucket(keys_not_all_in, flat_params)
    assert len(subdict_2) == 3


def test_param_fields_match_components_they_should_use(
    gridscan_params: GridscanInternalParameters,
    rotation_params: RotationInternalParameters,
):
    r_params = rotation_params.hyperion_params.ispyb_params
    g_params = gridscan_params.hyperion_params.ispyb_params

    r_calculated_ispyb_param_keys = list(
        rotation_params._hyperion_param_key_definitions()[2]
    )
    g_calculated_ispyb_param_keys = list(
        gridscan_params._hyperion_param_key_definitions()[2]
    )

    from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams

    base_ispyb_annotation_keys = list(IspybParams.__annotations__.keys())
    r_ispyb_annotation_keys = list(r_params.__class__.__annotations__.keys())
    g_ispyb_annotation_keys = list(g_params.__class__.__annotations__.keys())

    assert (
        r_calculated_ispyb_param_keys
        == base_ispyb_annotation_keys + r_ispyb_annotation_keys
    )
    assert (
        g_calculated_ispyb_param_keys
        == base_ispyb_annotation_keys + g_ispyb_annotation_keys
    )
    assert "upper_left" in g_ispyb_annotation_keys
    assert "upper_left" not in r_ispyb_annotation_keys


def test_internal_params_eq():
    params = external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )
    internal_params = GridscanInternalParameters(**params)
    internal_params_2 = copy.deepcopy(internal_params)

    assert internal_params == internal_params_2
    assert internal_params_2 != 3
    assert internal_params_2.hyperion_params != 3

    internal_params_2.experiment_params.x_steps = 11111
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.ispyb_params.beam_size_x = 123456
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.detector_params.exposure_time = 99999
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.zocalo_environment = "not_real_env"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.beamline = "not_real_beamline"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.insertion_prefix = "not_real_prefix"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.hyperion_params.experiment_type = "not_real_experiment"
    assert internal_params != internal_params_2
