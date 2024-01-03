from hyperion.parameters import external_parameters


def test_new_parameters_is_a_new_object():
    a = external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )
    b = external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )
    assert a == b
    assert a is not b


def test_parameters_load_from_file():
    params = external_parameters.from_file(
        "tests/test_data/parameter_json_files/test_parameters.json"
    )
    expt_params = params["experiment_params"]
    assert expt_params["x_steps"] == 5
    assert expt_params["y_steps"] == 10
    assert expt_params["z_steps"] == 2
    assert expt_params["x_step_size"] == 0.1
    assert expt_params["y_step_size"] == 0.1
    assert expt_params["z_step_size"] == 0.1
    assert expt_params["dwell_time_ms"] == 2
    assert expt_params["x_start"] == 0.0
    assert expt_params["y1_start"] == 0.0
    assert expt_params["y2_start"] == 0.0
    assert expt_params["z1_start"] == 0.0
    assert expt_params["z2_start"] == 0.0
