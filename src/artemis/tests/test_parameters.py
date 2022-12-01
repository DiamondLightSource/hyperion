from artemis.devices.fast_grid_scan import GridScanParams
from artemis.devices.rotation_scan import RotationScanParams
from artemis.parameters import FullParameters


def test_new_parameters_is_a_deep_copy():
    first_copy = FullParameters()
    second_copy = FullParameters()
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
    params = FullParameters.from_file("test_parameters.json")
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

    params = FullParameters.from_file("test_rotation_scan_parameters.json")
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
