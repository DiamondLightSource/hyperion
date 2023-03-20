import json

from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.rotation_scan import RotationScanParams
from pytest import raises

from artemis.parameters.external_parameters import (
    RawParameters,
    WrongExperimentParameterSpecification,
)


def test_new_parameters_is_a_deep_copy():
    first_copy = RawParameters()
    second_copy = RawParameters()
    assert first_copy == second_copy
    assert first_copy is not second_copy
    assert (
        first_copy.artemis_params.detector_params
        is not second_copy.artemis_params.detector_params
    )
    assert first_copy.experiment_params is not second_copy.experiment_params
    assert (
        first_copy.artemis_params.ispyb_params
        is not second_copy.artemis_params.ispyb_params
    )


def test_parameters_load_from_file():
    params = RawParameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    expt_params: GridScanParams = params.experiment_params
    assert isinstance(expt_params, GridScanParams)
    assert expt_params.x_steps == 5
    assert expt_params.y_steps == 10
    assert expt_params.z_steps == 2
    assert expt_params.x_step_size == 0.1
    assert expt_params.y_step_size == 0.1
    assert expt_params.z_step_size == 0.1
    assert expt_params.dwell_time == 0.2
    assert expt_params.x_start == 0.0
    assert expt_params.y1_start == 0.0
    assert expt_params.y2_start == 0.0
    assert expt_params.z1_start == 0.0
    assert expt_params.z2_start == 0.0

    params = RawParameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    )
    expt_params: RotationScanParams = params.experiment_params
    assert isinstance(params.experiment_params, RotationScanParams)
    assert expt_params.rotation_axis == "omega"
    assert expt_params.rotation_angle == 180.0
    assert expt_params.omega_start == 0.0
    assert expt_params.phi_start == 0.0
    assert expt_params.chi_start == 0
    assert expt_params.x == 1.0
    assert expt_params.y == 2.0
    assert expt_params.z == 3.0


def test_parameter_eq():
    params = RawParameters()

    assert not params == 6
    assert not params == ""

    params2 = RawParameters()
    assert params == params2
    params2.artemis_params.insertion_prefix = ""
    assert not params == params2

    params2 = RawParameters()
    assert params == params2
    params2.experiment_params.x_start = 12345
    assert not params == params2


def test_parameter_init_with_bad_type_raises_exception():
    with open(
        "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
    ) as f:
        param_dict = json.load(f)
    param_dict["artemis_params"]["experiment_type"] = "nonsense_scan"
    with raises(WrongExperimentParameterSpecification):
        params = RawParameters.from_dict(param_dict)  # noqa: F841
