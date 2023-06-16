import os

import pytest

from artemis.parameters.external_parameters import from_file
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def test_rotation_params():
    param_dict = from_file(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    )
    param_dict["artemis_params"]["detector_params"][
        "directory"
    ] = "src/artemis/external_interaction/unit_tests/test_data"
    param_dict["artemis_params"]["detector_params"]["prefix"] = "TEST_FILENAME"
    param_dict["experiment_params"]["rotation_angle"] = 360.0
    params = RotationInternalParameters(**param_dict)
    params.experiment_params.x = 0
    params.experiment_params.y = 0
    params.experiment_params.z = 0
    params.artemis_params.detector_params.exposure_time = 0.004
    params.artemis_params.detector_params.current_energy_ev = 12700
    params.artemis_params.ispyb_params.transmission = 0.49118047952
    params.artemis_params.ispyb_params.wavelength = 0.9762535433
    return params


@pytest.fixture(params=[1044])
def test_fgs_params(request):
    params = FGSInternalParameters(**default_raw_params())
    params.artemis_params.ispyb_params.wavelength = 1.0
    params.artemis_params.ispyb_params.flux = 9.0
    params.artemis_params.ispyb_params.transmission = 0.5
    params.artemis_params.detector_params.use_roi_mode = True
    params.artemis_params.detector_params.num_triggers = request.param
    params.artemis_params.detector_params.directory = (
        os.path.dirname(os.path.realpath(__file__)) + "/test_data"
    )
    params.artemis_params.detector_params.prefix = "dummy"
    yield params
