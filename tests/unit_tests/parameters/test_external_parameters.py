from os import environ
from unittest.mock import patch

from hyperion.parameters import external_parameters
from hyperion.parameters.beamline_parameters import (
    GDABeamlineParameters,
    get_beamline_parameters,
)


def test_new_parameters_is_a_new_object():
    a = external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/good_tests/parameter_json_files/test_parameters.json"
    )
    b = external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/good_tests/parameter_json_files/test_parameters.json"
    )
    assert a == b
    assert a is not b


def tests/parameter_json_files/test_parameters_load_from_file():
    params = external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/good_tests/parameter_json_files/test_parameters.json"
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


def test_beamline_parameters():
    params = GDABeamlineParameters.from_file(
        "src/hyperion/parameters/tests/test_data/test_beamline_parameters.txt"
    )
    assert params["sg_x_MEDIUM_APERTURE"] == 5.285
    assert params["col_parked_downstream_x"] == 0
    assert params["beamLineEnergy__pitchStep"] == 0.002
    assert params["DataCollection_TurboMode"] is True
    assert params["beamLineEnergy__adjustSlits"] is False


def test_i03_beamline_parameters():
    params = GDABeamlineParameters.from_file(
        "src/hyperion/parameters/tests/test_data/i04_beamlineParameters"
    )
    assert params["flux_predict_polynomial_coefficients_5"] == [
        -0.0000707134131045123,
        7.0205491504418,
        -194299.6440518530,
        1835805807.3974800,
        -3280251055671.100,
    ]


@patch("hyperion.parameters.beamline_parameters.LOGGER")
def test_parse_exception_causes_warning(mock_logger):
    params = GDABeamlineParameters.from_file(
        "src/hyperion/parameters/tests/test_data/bad_beamlineParameters"
    )
    assert params["flux_predict_polynomial_coefficients_5"] == [
        -0.0000707134131045123,
        7.0205491504418,
        -194299.6440518530,
        1835805807.3974800,
        -3280251055671.100,
    ]
    mock_logger.warning.assert_called_once()

    params = GDABeamlineParameters.from_file(
        "src/hyperion/parameters/tests/test_data/bad_beamlineParameters"
    )
    assert params["flux_predict_polynomial_coefficients_5"] == [
        -0.0000707134131045123,
        7.0205491504418,
        -194299.6440518530,
        1835805807.3974800,
        -3280251055671.100,
    ]


def test_parse_list():
    test_data = [([1, 2, 3], "[1, 2, 3]"), ([1, True, 3], "[1, Yes, 3]")]
    for expected, input in test_data:
        actual = GDABeamlineParameters.parse_value(input)
        assert expected == actual, f"Actual:{actual}, expected: {expected}\n"


def test_get_beamline_parameters_works_with_no_environment_variable_set():
    if environ.get("BEAMLINE"):
        del environ["BEAMLINE"]
    assert get_beamline_parameters()


def test_get_beamline_parameters():
    original_beamline = environ.get("BEAMLINE")
    environ["BEAMLINE"] = "i03"
    with patch.dict(
        "hyperion.parameters.beamline_parameters.BEAMLINE_PARAMETER_PATHS",
        {"i03": "src/hyperion/parameters/tests/test_data/test_beamline_parameters.txt"},
    ):
        params = get_beamline_parameters()
    assert params["col_parked_downstream_x"] == 0
    assert params["BackStopZyag"] == 19.1
    assert params["store_data_collections_in_ispyb"] is True
    assert params["attenuation_optimisation_type"] == "deadtime"
    if original_beamline:
        environ["BEAMLINE"] = original_beamline
    else:
        del environ["BEAMLINE"]
