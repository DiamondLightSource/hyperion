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
