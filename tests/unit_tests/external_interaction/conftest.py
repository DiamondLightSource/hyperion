import os

import pytest

from hyperion.parameters.external_parameters import from_file
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV


@pytest.fixture
def test_rotation_params():
    param_dict = from_file(
        "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
    )
    param_dict["hyperion_params"]["detector_params"]["directory"] = "tests/test_data"
    param_dict["hyperion_params"]["detector_params"]["prefix"] = "TEST_FILENAME"
    param_dict["hyperion_params"]["detector_params"]["current_energy_ev"] = 12700
    param_dict["hyperion_params"]["ispyb_params"]["current_energy_ev"] = 12700
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.hyperion_params.detector_params.exposure_time = 0.004
    params.hyperion_params.ispyb_params.transmission_fraction = 0.49118047952
    return params


@pytest.fixture(params=[1044])
def test_fgs_params(request):
    params = GridscanInternalParameters(**default_raw_params())
    params.hyperion_params.ispyb_params.current_energy_ev = convert_angstrom_to_eV(1.0)
    params.hyperion_params.ispyb_params.flux = 9.0
    params.hyperion_params.ispyb_params.transmission_fraction = 0.5
    params.hyperion_params.detector_params.current_energy_ev = convert_angstrom_to_eV(
        1.0
    )
    params.hyperion_params.detector_params.use_roi_mode = True
    params.hyperion_params.detector_params.num_triggers = request.param
    params.hyperion_params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.hyperion_params.detector_params.prefix = "dummy"
    yield params
