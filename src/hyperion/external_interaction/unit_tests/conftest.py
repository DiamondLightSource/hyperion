import os

import pytest

from hyperion.parameters.external_parameters import ExternalParameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV


@pytest.fixture
def test_rotation_params():
    raw_params = ExternalParameters.parse_file(
        "src/hyperion/parameters/tests/test_data/src/hyperion/parameters/tests/test_data/external_param_test_rotation.json"
    )
    raw_params.data_parameters.directory = (
        "src/hyperion/external_interaction/unit_tests/test_data"
    )
    raw_params.data_parameters.filename_prefix = "TEST_FILENAME"
    raw_params.experiment_parameters.energy_ev = 12700
    raw_params.experiment_parameters.scan_width_deg = 360.0
    params = RotationInternalParameters.from_external(raw_params)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.detector_params.exposure_time = 0.004
    params.ispyb_params.transmission_fraction = 0.49118047952
    return params


@pytest.fixture(params=[1044])
def test_fgs_params(request):
    params = GridscanInternalParameters.from_external(
        ExternalParameters.parse_file(
            "src/hyperion/parameters/tests/test_data/src/hyperion/parameters/tests/test_data/external_param_test_gridscan.json"
        )
    )
    params.ispyb_params.current_energy_ev = convert_angstrom_to_eV(1.0)
    params.ispyb_params.flux = 9.0
    params.ispyb_params.transmission_fraction = 0.5
    params.detector_params.current_energy_ev = convert_angstrom_to_eV(1.0)
    params.detector_params.use_roi_mode = True
    params.detector_params.num_triggers = request.param
    params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.detector_params.prefix = "dummy"
    yield params
