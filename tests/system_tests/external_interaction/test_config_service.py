from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np
import pytest
from daq_config_server.client import ConfigServer

from hyperion.external_interaction.config_server import config_server


@pytest.fixture
def config_service():
    return config_server()


@pytest.mark.s03
def test_get_beamline_params(config_service: ConfigServer):
    resp = config_service.get_beamline_param("miniap_x_SMALL_APERTURE")
    assert isinstance(resp, float)
    assert np.isclose(resp, 2.43)


@pytest.mark.s03
def test_get_feature_flag(config_service: ConfigServer):
    resp = config_service.get_feature_flag("set_stub_offsets")
    assert isinstance(resp, bool)


@pytest.mark.s03
def test_get_feature_flags(config_service: ConfigServer):
    features = config_service.best_effort_get_all_feature_flags()
    assert len(features.keys()) == 3


@pytest.mark.s03
def test_nonsense_feature_flag_fails_with_normal_call(config_service: ConfigServer):
    with pytest.raises(AssertionError):
        _ = config_service.get_feature_flag(str(uuid4()))


@pytest.mark.s03
def test_best_effort_gracefully_fails_with_nonsense(config_service: ConfigServer):
    resp = config_service.best_effort_get_feature_flag(str(uuid4()))
    assert resp is None


@pytest.mark.s03
def test_best_effort_gracefully_fails_if_service_down(config_service: ConfigServer):
    log_mock = MagicMock()
    config_service = ConfigServer("http://not_real_address", log_mock)
    resp = config_service.best_effort_get_feature_flag("set_stub_offsets")
    assert resp is None
    log_mock.error.assert_called_with(
        "Encountered an error reading from the config service.", exc_info=True
    )
