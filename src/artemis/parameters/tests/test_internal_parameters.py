from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

from artemis.parameters import external_parameters
from artemis.parameters.internal_parameters.internal_parameters import (
    InternalParameters,
    flatten_dict,
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


class TestParamType(AbstractExperimentParameterBase):
    trigger_number = "many_triggers"

    def get_num_images(self):
        return 15


class TestInternalParameters(InternalParameters):
    def pre_sorting_translation(self, param_dict: dict[str, Any]):
        pass

    def key_definitions(self):
        artemis_params = ["a", "b", "c"]
        detector_params = ["x", "y", "z"]
        ispyb_params = ["h", "k", "l"]
        return artemis_params, detector_params, ispyb_params

    experiment_params_type = TestParamType


class TestInternalParameters2(InternalParameters):
    def pre_sorting_translation(self, param_dict: dict[str, Any]):
        param_dict["q"] = param_dict["l"]

    def key_definitions(self):
        artemis_params = ["a", "b", "c"]
        detector_params = ["x", "y", "z"]
        ispyb_params = ["h", "k", "q"]
        return artemis_params, detector_params, ispyb_params

    experiment_params_type = TestParamType


def test_cant_initialise_abstract_internalparams():
    with pytest.raises(TypeError):
        internal_parameters = InternalParameters(  # noqa
            external_parameters.from_file()
        )


@dataclass
class TestArtemisParams:
    a: int
    b: int
    c: int
    detector_params: MagicMock
    ispyb_params: MagicMock


@patch(
    "artemis.parameters.internal_parameters.internal_parameters.ArtemisParameters",
    TestArtemisParams,
)
@patch("artemis.parameters.internal_parameters.internal_parameters.DetectorParams")
@patch("artemis.parameters.internal_parameters.internal_parameters.IspybParams")
def test_initialise_and_verify_transformation(
    ispybparams: MagicMock, detectorparams: MagicMock
):
    test_params = TestInternalParameters(TEST_PARAM_DICT)
    assert test_params.artemis_params.a == TEST_TRANSFORMED_PARAM_DICT["a"]
    assert test_params.artemis_params.b == TEST_TRANSFORMED_PARAM_DICT["b"]
    assert test_params.artemis_params.c == TEST_TRANSFORMED_PARAM_DICT["c"]
    test_params.artemis_params.detector_params == (
        TEST_TRANSFORMED_PARAM_DICT["detector_params"]
    )
    test_params.artemis_params.ispyb_params == (
        TEST_TRANSFORMED_PARAM_DICT["ispyb_params"]
    )


@patch(
    "artemis.parameters.internal_parameters.internal_parameters.ArtemisParameters",
    TestArtemisParams,
)
@patch("artemis.parameters.internal_parameters.internal_parameters.DetectorParams")
@patch("artemis.parameters.internal_parameters.internal_parameters.IspybParams")
def test_pre_sorting_transformation(ispybparams: MagicMock, detectorparams: MagicMock):
    test_params = TestInternalParameters2(TEST_PARAM_DICT)
    assert test_params.artemis_params.a == TEST_TRANSFORMED_PARAM_DICT_2["a"]
    assert test_params.artemis_params.b == TEST_TRANSFORMED_PARAM_DICT_2["b"]
    assert test_params.artemis_params.c == TEST_TRANSFORMED_PARAM_DICT_2["c"]
    test_params.artemis_params.detector_params == (
        TEST_TRANSFORMED_PARAM_DICT_2["detector_params"]
    )
    test_params.artemis_params.ispyb_params == (
        TEST_TRANSFORMED_PARAM_DICT_2["ispyb_params"]
    )


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
