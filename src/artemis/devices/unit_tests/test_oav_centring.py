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
        parameters._extract_dict_parameter("a_key_not_in_the_json", fallback_value=1)
        == 1
    )


def test_oav__extract_dict_parameter_not_found_fallback_value_not_present():
    parameters = OAVParameters("src/artemis/devices/unit_tests/test_OAVCentring.json")
    parameters.load_json()
    with pytest.raises(KeyError):
        parameters._extract_dict_parameter("a_key_not_in_the_json")


@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
def test_find_midpoint_symmetric_pin(
    fake_oav, fake_camera, fake_backlight, fake_goniometer
):
    centring = OAVCentring("src/artemis/devices/unit_tests/test_OAVCentring.json", "")
    x = np.arange(-10, 10, 20 / 1024)
    x2 = x**2
    top = -1 * x2 + 100
    bottom = x2 - 100

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = centring.find_midpoint(top, bottom)
    assert x_pos == 512


@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
def test_find_midpoint_non_symmetric_pin(
    fake_oav, fake_camera, fake_backlight, fake_goniometer
):
    centring = OAVCentring("src/artemis/devices/unit_tests/test_OAVCentring.json", "")
    x = np.arange(-2.35, 2.35, 4.7 / 1024)
    x2 = x**2
    x4 = x2**2
    top = -1 * x2 + 6
    bottom = x4 - 5 * x2 - 3

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = centring.find_midpoint(top, bottom)
    assert x_pos == 205
    # x = 205/1024*4.7 - 2.35 ≈ -1.41 which is the first stationary point of the width on
    # our midpoint line


@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
@pytest.mark.parametrize(
    "zoom_level,expected_xCentre,expected_yCentre",
    [(1.0, 368, 365), (5.0, 383, 353), (10.0, 381, 335)],
)
def test_extract_beam_position_different_beam_postitions(
    fake_oav,
    fake_camera,
    fake_backlight,
    fake_goniometer,
    zoom_level,
    expected_xCentre,
    expected_yCentre,
):
    centring = OAVCentring(
        "src/artemis/devices/unit_tests/test_OAVCentring.json",
        "src/artemis/devices/unit_tests/test_display.configuration",
    )
    centring.oav_parameters.zoom = zoom_level
    centring._extract_beam_position()
    assert centring.beam_centre_x == expected_xCentre
    assert centring.beam_centre_y == expected_yCentre
