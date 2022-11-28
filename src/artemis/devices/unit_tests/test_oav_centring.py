from unittest.mock import patch

import numpy as np
import pytest
from ophyd.sim import make_fake_device

from artemis.devices.backlight import Backlight
from artemis.devices.motors import I03Smargon
from artemis.devices.oav.oav_centring import OAVCentring, OAVParameters
from artemis.devices.oav.oav_detector import OAV, Camera
from artemis.devices.oav.oav_errors import (
    OAVError_WaveformAllZero,
    OAVError_ZoomLevelNotFound,
)

OAV_CENTRING_JSON = "src/artemis/devices/unit_tests/test_OAVCentring.json"
DISPLAY_CONFIGURATION = "src/artemis/devices/unit_tests/test_display.configuration"
ZOOM_LEVELS_XML = "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml"


@pytest.fixture
@patch("artemis.devices.oav.oav_centring.OAV")
@patch("artemis.devices.oav.oav_centring.OAV.wait_for_connection")
@patch("artemis.devices.oav.oav_centring.Camera")
@patch("artemis.devices.oav.oav_centring.Backlight")
@patch("artemis.devices.oav.oav_centring.I03Smargon")
def mock_centring(
    fake_oav,
    fake_wait_for_connection,
    fake_camera,
    fake_backlight,
    fake_i03smargon,
):
    centring = OAVCentring(
        OAV_CENTRING_JSON,
        DISPLAY_CONFIGURATION,
        ZOOM_LEVELS_XML,
        beamline="NOT A REAL BL OR SO3",
    )
    centring.oav_camera = make_fake_device(Camera)(name="camera")
    centring.oav = make_fake_device(OAV)(name="oav")
    centring.oav_backlight = make_fake_device(Backlight)(name="backlight")
    centring.oav_goniometer = make_fake_device(I03Smargon)(name="goniometer")
    return centring


@pytest.mark.parametrize(
    "parameter_name,expected_value",
    [("canny_edge_lower_threshold", 5.0), ("close_ksize", 11), ("direction", 1)],
)
def test_oav_parameters_load_parameters_from_json(parameter_name, expected_value):
    parameters = OAVParameters(OAV_CENTRING_JSON, ZOOM_LEVELS_XML)
    parameters.load_parameters_from_json()

    assert parameters.__dict__[parameter_name] == expected_value


def test_oav__extract_dict_parameter_not_found_fallback_value_present():
    parameters = OAVParameters(OAV_CENTRING_JSON, ZOOM_LEVELS_XML)
    parameters.load_json()
    assert (
        parameters._extract_dict_parameter("a_key_not_in_the_json", fallback_value=1)
        == 1
    )


def test_oav__extract_dict_parameter_not_found_fallback_value_not_present():
    parameters = OAVParameters(OAV_CENTRING_JSON, ZOOM_LEVELS_XML)
    parameters.load_json()
    with pytest.raises(KeyError):
        parameters._extract_dict_parameter("a_key_not_in_the_json")


def test_find_midpoint_symmetric_pin(mock_centring: OAVCentring):
    x = np.arange(-10, 10, 20 / 1024)
    x2 = x**2
    top = -1 * x2 + 100
    bottom = x2 - 100

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = mock_centring.find_midpoint(top, bottom)
    assert x_pos == 512


def test_all_zero_waveform(mock_centring: OAVCentring):
    x = np.zeros(1024)

    def fake_extract_data_from_pvs(*args):
        return 0, x, x, 0, 0, 0

    mock_centring.extract_data_from_pvs = fake_extract_data_from_pvs

    # set the waveforms to 0 before the edge is found
    with pytest.raises(OAVError_WaveformAllZero):
        (
            x_pos,
            y_pos,
            diff_at_x_pos,
            mid,
        ) = mock_centring.rotate_pin_and_collect_values(6)


def test_find_midpoint_non_symmetric_pin(mock_centring):
    x = np.arange(-2.35, 2.35, 4.7 / 1024)
    x2 = x**2
    x4 = x2**2
    top = -1 * x2 + 6
    bottom = x4 - 5 * x2 - 3

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = mock_centring.find_midpoint(top, bottom)
    assert x_pos == 205
    # x = 205/1024*4.7 - 2.35 ≈ -1.41 which is the first stationary point of the width on
    # our midpoint line


@pytest.mark.parametrize(
    "zoom_level,expected_xCentre,expected_yCentre",
    [(1.0, 368, 365), (5.0, 383, 353), (10.0, 381, 335)],
)
def test_extract_beam_position_different_beam_postitions(
    zoom_level,
    expected_xCentre,
    expected_yCentre,
    mock_centring: OAVCentring,
):
    mock_centring.oav_parameters.zoom = zoom_level
    mock_centring._extract_beam_position()
    assert mock_centring.beam_centre_x == expected_xCentre
    assert mock_centring.beam_centre_y == expected_yCentre


@pytest.mark.parametrize(
    "h,v,omega,expected_values",
    [
        (0.0, 0.0, 0.0, [0.0, 0.0, 0.0]),
        (10, 5, 90, [-10, 3.062e-16, 5]),
        (100, 50, 40, [-100, 38.302, 32.139]),
        (10, -100, -4, [-10, -99.756, 6.976]),
    ],
)
def test_distance_from_beam_centre_to_motor_coords_returns_the_same_values_as_GDA(
    h, v, omega, expected_values, mock_centring: OAVCentring
):
    results = np.around(
        mock_centring.distance_from_beam_centre_to_motor_coords(h, v, omega), decimals=2
    )
    expected_values = np.around(expected_values, decimals=2)
    assert np.array_equal(results, expected_values)


def test_get_rotation_increment_threshold_within_180(mock_centring: OAVCentring):
    mock_centring.oav_goniometer.omega.high_limit_travel.sim_put(180)
    mock_centring.oav_goniometer.omega.low_limit_travel.sim_put(0)
    mock_centring.oav_goniometer.omega.user_readback.sim_put(0)

    increment = mock_centring.get_rotation_increment(6, 0, 180)
    assert increment == 180 / 6


def test_get_rotation_increment_threshold_exceeded(mock_centring: OAVCentring):
    mock_centring.oav_goniometer.omega.high_limit_travel.sim_put(180)
    mock_centring.oav_goniometer.omega.low_limit_travel.sim_put(0)
    mock_centring.oav_goniometer.omega.user_readback.sim_put(0)

    increment = mock_centring.get_rotation_increment(6, 30, 180)
    assert increment == -180 / 6


def test_extract_goniometer_data_from_pvs(mock_centring: OAVCentring):
    mock_centring.oav_goniometer.omega.high_limit_travel.sim_put(180)
    mock_centring.oav_goniometer.omega.low_limit_travel.sim_put(0)
    mock_centring.oav_goniometer.omega.user_readback.sim_put(0)

    increment = mock_centring.get_rotation_increment(6, 30, 180)
    assert increment == -180 / 6


def test_get_edge_waveforms(mock_centring: OAVCentring):
    set_top = np.array([1, 2, 3, 4, 5])
    set_bottom = np.array([5, 4, 3, 2, 1])
    mock_centring.oav.top_pv.sim_put(set_top)
    mock_centring.oav.bottom_pv.sim_put(set_bottom)

    recieved_top, recieved_bottom = tuple(mock_centring.oav.get_edge_waveforms())
    assert np.array_equal(recieved_bottom.obj.value, set_bottom)
    assert np.array_equal(recieved_top.obj.value, set_top)


@pytest.mark.parametrize(
    "zoom_level,expected_microns_x,expected_microns_y",
    [(2.5, 2.31, 2.31), (15.0, 0.302, 0.302)],
)
def test_load_microns_per_pixel_entries_found(
    zoom_level, expected_microns_x, expected_microns_y, mock_centring: OAVCentring
):
    mock_centring.oav_parameters.load_microns_per_pixel(zoom_level)
    assert mock_centring.oav_parameters.micronsPerXPixel == expected_microns_x
    assert mock_centring.oav_parameters.micronsPerYPixel == expected_microns_y


def test_load_microns_per_pixel_entry_not_found(mock_centring: OAVCentring):
    with pytest.raises(OAVError_ZoomLevelNotFound):
        mock_centring.oav_parameters.load_microns_per_pixel(0.000001)
