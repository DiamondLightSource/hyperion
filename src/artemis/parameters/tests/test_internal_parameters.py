import copy
import json

import numpy as np
import pytest
from dodal.devices.detector import DetectorParams
from dodal.devices.fast_grid_scan import GridScanParams
from pydantic import ValidationError

from artemis.external_interaction.ispyb.ispyb_dataclass import (
    ISPYB_PARAM_DEFAULTS,
    IspybParams,
)
from artemis.parameters import external_parameters
from artemis.parameters.external_parameters import from_file
from artemis.parameters.internal_parameters import (
    ArtemisParameters,
    InternalParameters,
    extract_artemis_params_from_flat_dict,
    fetch_subdict_from_bucket,
    flatten_dict,
    get_extracted_experiment_and_flat_artemis_params,
)
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


@pytest.fixture
def raw_params():
    return external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )


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


def test_ispyb_param_dict():
    ispyb_params = IspybParams(**ISPYB_PARAM_DEFAULTS)
    as_dict = ispyb_params.dict()
    assert isinstance(as_dict.get("position"), list)
    modified_params = copy.deepcopy(ISPYB_PARAM_DEFAULTS)
    modified_params["position"] = [123, 7777777, 3]
    modified_ispyb_params = IspybParams(**modified_params)
    assert ispyb_params != modified_ispyb_params
    assert isinstance(modified_ispyb_params.position, np.ndarray)
    modified_as_dict = modified_ispyb_params.dict()
    assert modified_as_dict.get("position") == [123, 7777777, 3]


def test_internal_param_serialisation_deserialisation():
    data = from_file()
    internal_parameters = FGSInternalParameters(**data)

    serialised = internal_parameters.json(indent=2)
    reloaded = json.loads(serialised)

    deserialised = FGSInternalParameters(**reloaded)

    assert deserialised == internal_parameters


def test_flatten():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    flat_dict = flatten_dict(params)
    for k in flat_dict:
        assert not isinstance(flat_dict[k], dict)

    flat_test_dict = flatten_dict(TEST_PARAM_DICT)
    for k in ["a", "b", "c", "h", "k", "l", "x", "y", "z"]:
        assert k in flat_test_dict

    with pytest.raises(Exception):
        flatten_dict({"x": 6, "y": {"x": 7}})


def test_artemis_params_needs_values_from_experiment(raw_params):
    extracted_artemis_param_dict = extract_artemis_params_from_flat_dict(
        flatten_dict(raw_params)
    )
    with pytest.raises(ValidationError):
        artemis_params = ArtemisParameters(**extracted_artemis_param_dict)
    with pytest.raises(UnboundLocalError):
        assert artemis_params is not None


def test_artemis_params_can_be_deserialised_from_internal_representation(raw_params):
    internal_params = FGSInternalParameters(**raw_params)
    artemis_param_json = internal_params.artemis_params.json()
    artemis_param_dict = json.loads(artemis_param_json)
    assert artemis_param_dict.get("ispyb_params") is not None
    assert artemis_param_dict.get("detector_params") is not None
    artemis_params_deserialised = ArtemisParameters(**artemis_param_dict)
    assert internal_params.artemis_params == artemis_params_deserialised
    ispyb = artemis_params_deserialised.ispyb_params
    detector = artemis_params_deserialised.detector_params
    assert isinstance(ispyb, IspybParams)
    assert isinstance(detector, DetectorParams)


def test_artemis_params_eq(raw_params):
    internal_params = FGSInternalParameters(**raw_params)

    artemis_params_1 = internal_params.artemis_params
    artemis_params_2 = copy.deepcopy(artemis_params_1)
    assert artemis_params_1 == artemis_params_2

    artemis_params_2.zocalo_environment = "some random thing"
    assert artemis_params_1 != artemis_params_2

    artemis_params_2 = copy.deepcopy(artemis_params_1)
    artemis_params_2.insertion_prefix = "some random thing"
    assert artemis_params_1 != artemis_params_2

    artemis_params_2 = copy.deepcopy(artemis_params_1)
    artemis_params_2.experiment_type = "some random thing"
    assert artemis_params_1 != artemis_params_2

    artemis_params_2 = copy.deepcopy(artemis_params_1)
    artemis_params_2.detector_params.current_energy_ev = 99999
    assert artemis_params_1 != artemis_params_2

    artemis_params_2 = copy.deepcopy(artemis_params_1)
    artemis_params_2.ispyb_params.beam_size_x = 99999
    assert artemis_params_1 != artemis_params_2


def test_get_extracted_experiment_and_flat_artemis_params(raw_params):
    flat_params = flatten_dict(raw_params)
    processed_params = get_extracted_experiment_and_flat_artemis_params(
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


def test_internal_params_eq():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    internal_params = FGSInternalParameters(**params)
    internal_params_2 = copy.deepcopy(internal_params)

    assert internal_params == internal_params_2
    assert internal_params_2 != 3
    assert internal_params_2.artemis_params != 3

    internal_params_2.experiment_params.x_steps = 11111
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.ispyb_params.beam_size_x = 123456
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.detector_params.exposure_time = 99999
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.zocalo_environment = "not_real_env"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.beamline = "not_real_beamline"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.insertion_prefix = "not_real_prefix"
    assert internal_params != internal_params_2

    internal_params_2 = copy.deepcopy(internal_params)
    internal_params_2.artemis_params.experiment_type = "not_real_experiment"
    assert internal_params != internal_params_2
