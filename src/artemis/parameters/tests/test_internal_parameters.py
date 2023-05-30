import copy
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

from artemis.parameters import external_parameters
from artemis.parameters.external_parameters import from_file
from artemis.parameters.internal_parameters import InternalParameters, flatten_dict
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters

TEST_PARAM_DICT = {
    "layer_1": {
        "a": 23,
        "x": 56,
        "k": 47,
        "layer_2": {"l": 11, "h": "test_value"},
        "layer_3": {"b": 5, "c": 6, "y": 7, "z": "test_value_2"},
    }
}

TEST_TRANSFORMED_PARAM_DICT: dict[str, Any] = {
    "a": 23,
    "b": 5,
    "c": 6,
    "detector_params": {"x": 56, "y": 7, "z": "test_value_2"},
    "ispyb_params": {"h": "test_value", "k": 47, "l": 11},
}

TEST_TRANSFORMED_PARAM_DICT_2: dict[str, Any] = {
    "a": 23,
    "b": 5,
    "c": 6,
    "detector_params": {"x": 56, "y": 7, "z": "test_value_2"},
    "ispyb_params": {"h": "test_value", "k": 47, "q": 11},
}


class ParamTypeForTesting(AbstractExperimentParameterBase):
    def get_num_images(self):
        return 15


class InternalParametersSubclassForTesting(InternalParameters):
    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        pass

    def key_definitions(self):
        artemis_params = ["a", "b", "c"]
        detector_params = ["x", "y", "z"]
        ispyb_params = ["h", "k", "l"]
        return artemis_params, detector_params, ispyb_params

    experiment_params_type = ParamTypeForTesting


class InternalParametersSubclass2(InternalParameters):
    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        param_dict["q"] = param_dict["l"]

    def key_definitions(self):
        artemis_params = ["a", "b", "c"]
        detector_params = ["x", "y", "z"]
        ispyb_params = ["h", "k", "q"]
        return artemis_params, detector_params, ispyb_params

    experiment_params_type = ParamTypeForTesting


@dataclass
class FakeArtemisParams:
    a: int
    b: int
    c: int
    detector_params: MagicMock
    ispyb_params: MagicMock


def test_cant_initialise_abstract_internalparams():
    with pytest.raises(TypeError):
        internal_parameters = InternalParameters(  # noqa
            external_parameters.from_file()
        )


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
