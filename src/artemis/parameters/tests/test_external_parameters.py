from os import environ
from unittest.mock import patch

import pytest

from artemis.parameters import external_parameters
from artemis.parameters.beamline_parameters import (
    BeamlinePrefixes,
    GDABeamlineParameters,
    get_beamline_parameters,
    get_beamline_prefixes,
)


def test_new_parameters_is_a_new_object():
    a = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    b = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    assert a == b
    assert a is not b


def test_parameters_load_from_file():
    params = external_parameters.from_file(
        "src/artemis/parameters/tests/test_data/good_test_parameters.json"
    )
    expt_params = params["experiment_params"]
    assert expt_params["x_steps"] == 5
    assert expt_params["y_steps"] == 10
    assert expt_params["z_steps"] == 2
    assert expt_params["x_step_size"] == 0.1
    assert expt_params["y_step_size"] == 0.1
    assert expt_params["z_step_size"] == 0.1
    assert expt_params["dwell_time"] == 0.2
    assert expt_params["x_start"] == 0.0
    assert expt_params["y1_start"] == 0.0
    assert expt_params["y2_start"] == 0.0
    assert expt_params["z1_start"] == 0.0
    assert expt_params["z2_start"] == 0.0


def test_beamline_parameters():
    params = GDABeamlineParameters.from_file(
        "src/artemis/parameters/tests/test_data/test_beamline_parameters.txt"
    )
    assert params["sg_x_MEDIUM_APERTURE"] == 5.285
    assert params["col_parked_downstream_x"] == 0
    assert params["beamLineEnergy__pitchStep"] == 0.002
    assert params["DataCollection_TurboMode"] is True
    assert params["beamLineEnergy__adjustSlits"] is False


def test_get_beamline_parameters_works_with_no_environment_variable_set():
    if environ.get("BEAMLINE"):
        del environ["BEAMLINE"]
    assert get_beamline_parameters()


def test_get_beamline_parameters():
    original_beamline = environ.get("BEAMLINE")
    environ["BEAMLINE"] = "i03"
    with patch.dict(
        "artemis.parameters.beamline_parameters.BEAMLINE_PARAMETER_PATHS",
        {"i03": "src/artemis/parameters/tests/test_data/test_beamline_parameters.txt"},
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


def test_beamline_prefixes():
    original_beamline = environ.get("BEAMLINE")
    if original_beamline:
        del environ["BEAMLINE"]
    assert get_beamline_prefixes() == BeamlinePrefixes("BL03S", "SR03S")
    environ["BEAMLINE"] = "i03"
    assert get_beamline_prefixes() == BeamlinePrefixes("BL03I", "SR03I")
    environ["BEAMLINE"] = "i571"
    with pytest.raises(Exception) as excinfo:
        get_beamline_prefixes()
    assert "i571 is not currently supported" in str(excinfo.value)
    if original_beamline:
        environ["BEAMLINE"] = original_beamline
    else:
        del environ["BEAMLINE"]
