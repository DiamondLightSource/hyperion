from uuid import uuid4

import numpy as np
import pytest
from config_service.client import ConfigService


@pytest.fixture
def config_service():
    return ConfigService("localhost", 8000)


def test_get_beamline_params(config_service: ConfigService):
    resp = config_service.get_beamline_param("miniap_x_SMALL_APERTURE")
    assert isinstance(resp, float)
    assert np.isclose(resp, 2.459)


def test_get_feature_flag(config_service: ConfigService):
    resp = config_service.get_feature_flag("set_stub_offsets")
    assert isinstance(resp, bool)
    assert resp


def test_nonsense_feature_flag_is_none(config_service: ConfigService):
    resp = config_service.get_feature_flag(str(uuid4()))
    assert resp is None
