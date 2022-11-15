from unittest.mock import patch

import numpy as np
import pytest

from artemis.devices.oav.oav_centring import OAVCentring, OAVParameters


@pytest.mark.parametrize(
    "parameter_name,expected_value",
    [("canny_edge_lower_threshold", 5.0), ("close_ksize", 11), ("direction", 1)],
)
def test_oav_parameters_load_parameters_from_json(parameter_name, expected_value):
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_parameters_from_json()

    assert parameters.__dict__[parameter_name] == expected_value


def test_oav__extract_dict_parameter_not_found_fallback_value_present():
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_json()
    assert (
        parameters._extract_dict_parameter(
            "loopCentring", "a_key_not_in_the_json", fallback_value=1
        )
        == 1
    )


def test_oav__extract_dict_parameter_not_found_fallback_value_not_present():
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_json()
    with pytest.raises(KeyError):
        parameters._extract_dict_parameter("loopCentring", "a_key_not_in_the_json")


@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
def test_find_midpoint_symmetric_pin(
    fake_oav, fake_camera, fake_backlight, fake_goniometer
):
    centring = OAVCentring("src/artemis/devices/unit_tests/test_OAVCentring.json")
    centring.oav_parameters.crossing_to_use = 0
    x_squared = np.square(np.arange(-10, 10, 20 / 1024))
    top = -1 * x_squared + 100
    bottom = x_squared - 100
    (x_pos, y_pos, diff_at_x_pos, mid) = centring.find_midpoint(top, bottom)
    assert x_pos == 512


@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
def test_find_midpoint_non_symmetric_pin(
    fake_oav, fake_camera, fake_backlight, fake_goniometer
):
    centring = OAVCentring("src/artemis/devices/unit_tests/test_OAVCentring.json")
    centring.oav_parameters.crossing_to_use = 0
    x_squared = np.square(np.arange(-2.35, 2.35, 4.7 / 1024))
    x_pow4 = np.square(x_squared)
    top = -1 * x_squared + 6
    bottom = x_pow4 - 5 * x_squared - 3
    (x_pos, y_pos, diff_at_x_pos, mid) = centring.find_midpoint(top, bottom)
    assert x_pos == 205
    # x = 205/1024*4.7 - 2.35 ≈ -1.41 which is the first stationary point on our midpoint line
