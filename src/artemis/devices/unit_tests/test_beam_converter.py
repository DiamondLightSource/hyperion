import pytest
from mockito import when
from src.artemis.devices.det_dist_to_beam_converter import DetectorDistanceToBeamXYConverter


LOOKUP_TABLE_TEST_VALUES = [[100.0, 200.0], [150.0, 151.0], [160.0, 165.0]]


@pytest.fixture
def fake_converter() -> DetectorDistanceToBeamXYConverter:
    when(DetectorDistanceToBeamXYConverter).parse_table().thenReturn(LOOKUP_TABLE_TEST_VALUES)
    return DetectorDistanceToBeamXYConverter('test.txt')


@pytest.mark.parametrize(
    "detector_distance, axis, expected_value",
    [
        (100.0, 'x', 160.0),
        (200.0, 'y', 151.0),
        (150.0, 'y', 150.5),
        (190.0, 'x', 164.5)
    ]
)
def test_interpolate_beam_xy_from_det_distance(fake_converter, detector_distance: float, axis: str, expected_value: float):
    axis_index = 1 if axis == 'y' else 2
    assert fake_converter.get_beam_xy_from_det_dist_mm(detector_distance, LOOKUP_TABLE_TEST_VALUES[axis_index]) == expected_value


def test_get_beam_in_pixels(fake_converter):
    detector_distance = 100.0
    image_size_pixels = 100
    detector_dimensions = 200.0
    interpolated_x_value = 160.0
    interpolated_y_value = 150.0

    when(fake_converter).get_beam_xy_from_det_dist_mm(100.0, LOOKUP_TABLE_TEST_VALUES[1]).thenReturn(interpolated_y_value)
    when(fake_converter).get_beam_xy_from_det_dist_mm(100.0, LOOKUP_TABLE_TEST_VALUES[2]).thenReturn(interpolated_x_value)
    expected_y_value = interpolated_y_value * image_size_pixels / detector_dimensions
    expected_x_value = interpolated_x_value * image_size_pixels / detector_dimensions

    assert fake_converter.get_beam_y_pixels(detector_distance, image_size_pixels, detector_dimensions) == expected_y_value
    assert fake_converter.get_beam_x_pixels(detector_distance, image_size_pixels, detector_dimensions) == expected_x_value


def test_parse_table():
    test_file = 'test_beam_converter.py'
    test_converter = DetectorDistanceToBeamXYConverter(test_file)

    assert test_converter.lookup_file == test_file
    assert test_converter.lookup_table_values == LOOKUP_TABLE_TEST_VALUES

    test_converter.reload_lookup_table()

    assert test_converter.lookup_file == test_file
    assert test_converter.lookup_table_values == LOOKUP_TABLE_TEST_VALUES
