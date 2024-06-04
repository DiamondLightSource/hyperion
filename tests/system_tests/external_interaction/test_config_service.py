from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np
import pytest
from config_service.client import ConfigService

from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST


@pytest.fixture
def config_service():
    return ConfigService(*CONST.CONFIG_SERVICE_ADDRESS, LOGGER)


@pytest.mark.s03
def test_get_beamline_params(config_service: ConfigService):
    resp = config_service.get_beamline_param("miniap_x_SMALL_APERTURE")
    assert isinstance(resp, float)
    assert np.isclose(resp, 2.459)


@pytest.mark.s03
def test_get_feature_flag(config_service: ConfigService):
    resp = config_service.get_feature_flag("set_stub_offsets")
    assert isinstance(resp, bool)
    assert resp


@pytest.mark.s03
def test_nonsense_feature_flag_is_none(config_service: ConfigService):
    resp = config_service.get_feature_flag(str(uuid4()))
    assert resp is None


@pytest.mark.s03
def test_best_effort_gracefully_fails():
    log_mock = MagicMock()
    config_service = ConfigService("not_real_address", 9999, log_mock)
    resp = config_service.best_effort_get_feature_flag("set_stub_offsets")
    assert resp is None
    log_mock.error.assert_called_with(
        "Encountered an error reading from the config service.", exc_info=True
    )
