import copy
import json

import numpy as np
import pytest

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    GRIDSCAN_ISPYB_PARAM_DEFAULTS,
    GridscanIspybParams,
)
from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.internal_parameters import (
    InternalParameters,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
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


def test_gridscan_parameters_from_external():
    with open(
        "src/hyperion/parameters/tests/test_data/external_param_test_gridscan.json"
    ) as f:
        data = json.loads(f.read())
    external_params = ExternalParameters.parse_obj(data)
    external_params.experiment_type = "flyscan_xray_centre"
    internal_params = GridscanInternalParameters.from_external(external_params)
    assert internal_params.ispyb_params.comment == "Comment."
    assert internal_params.detector_params.current_energy_ev == 12700

    scan_1_num_images = len(internal_params.get_scan_points(1)["sam_x"])
    scan_2_num_images = len(internal_params.get_scan_points(2)["sam_x"])
    assert (
        scan_1_num_images
        == internal_params.experiment_params.x_steps
        * internal_params.experiment_params.y_steps
    )
    assert (
        scan_2_num_images
        == internal_params.experiment_params.x_steps
        * internal_params.experiment_params.z_steps
    )
    assert (
        internal_params.detector_params.num_triggers
        == scan_1_num_images + scan_2_num_images
    )


def test_rotation_parameters_from_external():
    with open(
        "src/hyperion/parameters/tests/test_data/external_param_test_rotation.json"
    ) as f:
        data = json.loads(f.read())
    external_params = ExternalParameters.parse_obj(data)
    external_params.experiment_type = "rotation_scan"
    internal_params = RotationInternalParameters.from_external(external_params)
    assert internal_params.ispyb_params.comment == "Comment."
    assert internal_params.detector_params.current_energy_ev == 12700
    assert internal_params.experiment_params.get_num_images == 365
