# from unittest.mock import patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from ophyd.sim import make_fake_device

from artemis.devices.backlight import Backlight
from artemis.devices.motors import I03Smargon
from artemis.devices.oav.oav_centring_plan import (
    distance_from_beam_centre_to_motor_coords,
    find_midpoint,
    get_rotation_increment,
)
from artemis.devices.oav.oav_detector import OAV
from artemis.devices.oav.oav_errors import OAVError_ZoomLevelNotFound
from artemis.devices.oav.oav_parameters import OAVParameters

OAV_CENTRING_JSON = "src/artemis/devices/unit_tests/test_OAVCentring.json"
DISPLAY_CONFIGURATION = "src/artemis/devices/unit_tests/test_display.configuration"
ZOOM_LEVELS_XML = "src/artemis/devices/unit_tests/test_jCameraManZoomLevels.xml"


def do_nothing(*args):
    pass


@pytest.fixture
def mock_oav():
    oav: OAV = make_fake_device(OAV)(name="oav", prefix="a fake beamline")
    oav.wait_for_connection = do_nothing
    return oav


@pytest.fixture
def mock_parameters():
    return OAVParameters(OAV_CENTRING_JSON, ZOOM_LEVELS_XML, DISPLAY_CONFIGURATION)


@pytest.fixture
def mock_smargon():
    smargon: I03Smargon = make_fake_device(I03Smargon)(name="smargon")
    smargon.wait_for_connection = do_nothing
    return smargon


@pytest.fixture
def mock_backlight():
    backlight: Backlight = make_fake_device(Backlight)(name="backlight")
    backlight.wait_for_connection = do_nothing
    return backlight


def test_can_make_fake_testing_devices_and_use_run_engine(
    mock_oav: OAV,
    mock_parameters: OAVParameters,
    mock_smargon: I03Smargon,
    mock_backlight: Backlight,
):
    @bpp.run_decorator()
    def fake_run(mock_oav, mock_parameters, mock_smargon, mock_backlight):
        yield from bps.abs_set(mock_oav.cam.acquire_period, 5)
        mock_parameters.acquire_period = 10
        # can't change the smargon motors because of limit issues with FakeEpicsDevice
        # yield from bps.mv(mock_smargon.omega, 1)
        yield from bps.mv(mock_backlight.pos, 1)

    RE = RunEngine()
    RE(fake_run(mock_oav, mock_parameters, mock_smargon, mock_backlight))


@pytest.mark.parametrize(
    "parameter_name,expected_value",
    [("canny_edge_lower_threshold", 5.0), ("close_ksize", 11), ("direction", 1)],
)
def test_oav_parameters_load_parameters_from_json(
    parameter_name, expected_value, mock_parameters: OAVParameters
):

    mock_parameters.load_parameters_from_json()

    assert mock_parameters.__dict__[parameter_name] == expected_value


def test_oav__extract_dict_parameter_not_found_fallback_value_present(
    mock_parameters: OAVParameters,
):
    mock_parameters.load_json()
    assert (
        mock_parameters._extract_dict_parameter(
            "a_key_not_in_the_json", fallback_value=1
        )
        == 1
    )


def test_oav__extract_dict_parameter_not_found_fallback_value_not_present(
    mock_parameters: OAVParameters,
):
    mock_parameters.load_json()
    with pytest.raises(KeyError):
        mock_parameters._extract_dict_parameter("a_key_not_in_the_json")


def test_find_midpoint_symmetric_pin():
    x = np.arange(-10, 10, 20 / 1024)
    x2 = x**2
    top = -1 * x2 + 100
    bottom = x2 - 100

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = find_midpoint(top, bottom)
    assert x_pos == 512


def test_find_midpoint_non_symmetric_pin():
    x = np.arange(-2.35, 2.35, 4.7 / 1024)
    x2 = x**2
    x4 = x2**2
    top = -1 * x2 + 6
    bottom = x4 - 5 * x2 - 3

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, diff_at_x_pos, mid) = find_midpoint(top, bottom)
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
    mock_oav: OAV,
    mock_parameters: OAVParameters,
):
    mock_parameters.zoom = zoom_level
    mock_parameters._extract_beam_position()
    assert mock_parameters.beam_centre_x == expected_xCentre
    assert mock_parameters.beam_centre_y == expected_yCentre


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
    h, v, omega, expected_values
):
    results = np.around(
        distance_from_beam_centre_to_motor_coords(h, v, omega), decimals=2
    )
    expected_values = np.around(expected_values, decimals=2)
    assert np.array_equal(results, expected_values)


def test_get_rotation_increment_threshold_within_180(
    mock_oav: OAV, mock_smargon: I03Smargon
):
    increment = get_rotation_increment(6, 0, 180)
    assert increment == 180 / 6


def test_get_rotation_increment_threshold_exceeded():
    increment = get_rotation_increment(6, 30, 180)
    assert increment == -180 / 6


@pytest.mark.parametrize(
    "zoom_level,expected_microns_x,expected_microns_y",
    [(2.5, 2.31, 2.31), (15.0, 0.302, 0.302)],
)
def test_load_microns_per_pixel_entries_found(
    zoom_level, expected_microns_x, expected_microns_y, mock_parameters: OAVParameters
):
    mock_parameters.load_microns_per_pixel(zoom_level)
    assert mock_parameters.micronsPerXPixel == expected_microns_x
    assert mock_parameters.micronsPerYPixel == expected_microns_y


def test_load_microns_per_pixel_entry_not_found(mock_parameters: OAVParameters):
    with pytest.raises(OAVError_ZoomLevelNotFound):
        mock_parameters.load_microns_per_pixel(0.000001)


@pytest.mark.parametrize(
    "value,lower_bound,upper_bound,expected_value",
    [(0.5, -10, 10, 0.5), (-100, -10, 10, -10), (10000, -213, 50, 50)],
)
def test_keep_inside_bounds(value, lower_bound, upper_bound, expected_value):
    from artemis.devices.oav.oav_centring_plan import keep_inside_bounds

    assert keep_inside_bounds(value, lower_bound, upper_bound) == expected_value


# Can't run the below test without decent FakeEpicsDevice motors.
"""
def test_all_zero_waveform(fake_mv, mock_oav: OAV, mock_smargon: I03Smargon):

    x = np.zeros(1024)

    def fake_run(mock_oav: OAV, mock_smargon: I03Smargon):
        mock_smargon.wait_for_connection = do_nothing
        yield from bps.abs_set(mock_smargon.omega, 0)
        yield from bps.abs_set(mock_oav.mxsc.top, x)
        yield from bps.abs_set(mock_oav.mxsc.bottom, x)
        yield from bps.abs_set(mock_oav.mxsc.tip_x, 0)
        yield from bps.abs_set(mock_oav.mxsc.tip_y, 0)

        (
            x_pos,
            y_pos,
            diff_at_x_pos,
            mid,
        ) = rotate_pin_and_collect_values(mock_oav, mock_smargon, 6)

    with pytest.raises(OAVError_WaveformAllZero):
        RE = RunEngine()
        RE(
            fake_run(mock_oav, mock_smargon),
        )


"""

"""
def test_all_zero_waveform(fake_mv, mock_oav: OAV, mock_smargon: I03Smargon):

    x = np.zeros(1024)

    def fake_run(mock_oav: OAV, mock_smargon: I03Smargon):
        mock_smargon.wait_for_connection = do_nothing
        yield from bps.abs_set(mock_smargon.omega, 0)
        yield from bps.abs_set(mock_oav.mxsc.top, x)
        yield from bps.abs_set(mock_oav.mxsc.bottom, x)
        yield from bps.abs_set(mock_oav.mxsc.tip_x, 0)
        yield from bps.abs_set(mock_oav.mxsc.tip_y, 0)

        (
            x_pos,
            y_pos,
            diff_at_x_pos,
            mid,
        ) = rotate_pin_and_collect_values(mock_oav, mock_smargon, 6)

    with pytest.raises(OAVError_WaveformAllZero):
        RE = RunEngine()
        RE(
            fake_run(mock_oav, mock_smargon),
        )


"""
