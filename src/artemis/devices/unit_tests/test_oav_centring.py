# from unittest.mock import patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from ophyd.sim import make_fake_device

from artemis.devices.backlight import Backlight
from artemis.devices.I03Smargon import I03Smargon
from artemis.devices.oav.oav_calculations import (
    camera_coordinates_to_xyz,
    check_i_within_bounds,
    extract_pixel_centre_values_from_rotation_data,
    filter_rotation_data,
    find_midpoint,
    find_widest_point_and_orthogonal_point,
    get_orthogonal_index,
    get_rotation_increment,
)
from artemis.devices.oav.oav_detector import OAV
from artemis.devices.oav.oav_errors import (
    OAVError_MissingRotations,
    OAVError_NoRotationsPassValidityTest,
    OAVError_ZoomLevelNotFound,
)
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
    x = np.arange(-15, 10, 25 / 1024)
    x2 = x**2
    top = -1 * x2 + 100
    bottom = x2 - 100
    top += 500
    bottom += 500

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, width) = find_midpoint(top, bottom)
    assert x_pos == 614
    assert y_pos == 500


def test_find_midpoint_non_symmetric_pin():
    x = np.arange(-4, 2.35, 6.35 / 1024)
    x2 = x**2
    x4 = x2**2
    top = -1 * x2 + 6
    bottom = x4 - 5 * x2 - 3

    top += 400
    bottom += 400

    # set the waveforms to 0 before the edge is found
    top[np.where(top < bottom)[0]] = 0
    bottom[np.where(bottom > top)[0]] = 0

    (x_pos, y_pos, width) = find_midpoint(top, bottom)
    assert x_pos == 419
    assert np.floor(y_pos) == 397
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
    assert mock_parameters.beam_centre_i == expected_xCentre
    assert mock_parameters.beam_centre_j == expected_yCentre


def test_get_rotation_increment_threshold_within_180():
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


@pytest.mark.parametrize(
    "h, v, expected_x, expected_y",
    [
        (54, 100, 383 - 54, 353 - 100),
        (0, 0, 383, 353),
        (500, 500, 383 - 500, 353 - 500),
    ],
)
def test_calculate_beam_distance(
    h, v, expected_x, expected_y, mock_parameters: OAVParameters
):
    assert mock_parameters.calculate_beam_distance(
        h,
        v,
    ) == (expected_x, expected_y)


def test_filter_rotation_data():
    x_positions = np.array([400, 450, 7, 500])
    y_positions = np.array([400, 450, 7, 500])
    widths = np.array([400, 450, 7, 500])
    omegas = np.array([400, 450, 7, 500])

    (
        filtered_x,
        filtered_y,
        filtered_widths,
        filtered_omegas,
    ) = filter_rotation_data(x_positions, y_positions, widths, omegas)

    assert filtered_x[2] == 500
    assert filtered_omegas[2] == 500


def test_filter_rotation_data_throws_error_when_all_fail():
    x_positions = np.array([1020, 20])
    y_positions = np.array([10, 450])
    widths = np.array([400, 450])
    omegas = np.array([400, 450])
    with pytest.raises(OAVError_NoRotationsPassValidityTest):
        (
            filtered_x,
            filtered_y,
            filtered_widths,
            filtered_omegas,
        ) = filter_rotation_data(x_positions, y_positions, widths, omegas)


@pytest.mark.parametrize(
    "max_tip_distance, tip_x, x, expected_return",
    [
        (180, 400, 600, 580),
        (180, 400, 450, 450),
    ],
)
def test_keep_x_within_bounds(max_tip_distance, tip_x, x, expected_return):
    assert check_i_within_bounds(max_tip_distance, tip_x, x) == expected_return


@pytest.mark.parametrize(
    "h,v,omega,expected_values",
    [
        (0.0, 0.0, 0.0, np.array([0.0, 0.0, 0.0])),
        (10, -5, 90, np.array([-10, 3.062e-16, -5])),
        (100, -50, 40, np.array([-100, 38.302, -32.139])),
        (10, 100, -4, np.array([-10, -99.756, -6.976])),
    ],
)
def test_distance_from_beam_centre_to_motor_coords_returns_the_same_values_as_GDA(
    h, v, omega, expected_values, mock_parameters: OAVParameters
):

    mock_parameters.zoom = 5.0
    mock_parameters.load_microns_per_pixel()
    results = camera_coordinates_to_xyz(
        h,
        v,
        omega,
        mock_parameters.micronsPerXPixel,
        mock_parameters.micronsPerYPixel,
    )
    expected_values = expected_values * 1e-3
    expected_values[0] *= mock_parameters.micronsPerXPixel
    expected_values[1] *= mock_parameters.micronsPerYPixel
    expected_values[2] *= mock_parameters.micronsPerYPixel
    expected_values = np.around(expected_values, decimals=3)

    assert np.array_equal(np.around(results, decimals=3), expected_values)


def test_find_widest_point_and_orthogonal_point():
    widths = np.array([400, 450, 7, 500, 600, 400])
    omegas = np.array([0, 30, 60, 90, 120, 180])
    assert find_widest_point_and_orthogonal_point(widths, omegas) == (4, 1)


def test_find_widest_point_and_orthogonal_point_no_orthogonal_angles():
    widths = np.array([400, 7, 500, 600, 400])
    omegas = np.array([0, 60, 90, 120, 180])
    with pytest.raises(OAVError_MissingRotations):
        find_widest_point_and_orthogonal_point(widths, omegas)


def test_extract_pixel_centre_values_from_rotation_data():
    x_positions = np.array([400, 450, 7, 500, 475, 412])
    y_positions = np.array([500, 512, 518, 498, 486, 530])
    widths = np.array([400, 450, 7, 500, 600, 400])
    omegas = np.array([0, 30, 60, 90, 120, 180])
    assert extract_pixel_centre_values_from_rotation_data(
        x_positions, y_positions, widths, omegas
    ) == (475, 486, 512, 120, 30)


@pytest.mark.parametrize(
    "angle_array,angle,expected_index",
    [
        (np.array([0, 30, 60, 90, 140, 180, 210, 240, 250, 255]), 50, 4),
        (np.array([0, 30, 60, 90, 145, 180, 210, 240, 250, 255]), 50, 4),
        (np.array([-40, 30, 60, 90, 145, 180, 210, 240, 250, 255]), 50, 0),
        (np.array([-150, -120, -90, -60, -30, 0, 30]), 30, 3),
    ],
)
def test_get_closest_orthogonal_index(angle_array, angle, expected_index):
    assert get_orthogonal_index(angle_array, angle) == expected_index


def test_get_closest_orthogonal_index_not_orthogonal_enough():
    with pytest.raises(OAVError_MissingRotations):
        get_orthogonal_index(
            np.array([0, 30, 60, 90, 160, 180, 210, 240, 250, 255]), 50
        )
