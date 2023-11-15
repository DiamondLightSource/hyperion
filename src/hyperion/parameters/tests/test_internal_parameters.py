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
from hyperion.parameters import jsonschema_external_parameters
from hyperion.parameters.internal_parameters import (
    InternalParameters,
)
from hyperion.parameters.jsonschema_external_parameters import from_file
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def raw_params():
    return jsonschema_external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/good_test_parameters.json"
    )


@pytest.fixture
def rotation_raw_params():
    return jsonschema_external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
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
            **jsonschema_external_parameters.from_file()
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
