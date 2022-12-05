import pytest
from mockito import when

from artemis.devices.det_dist_to_beam_converter import (
    Axis,
    DetectorDistanceToBeamXYConverter,
)

LOOKUP_TABLE_TEST_VALUES = [(100.0, 200.0), (150.0, 151.0), (160.0, 165.0)]


@pytest.fixture
def fake_converter() -> DetectorDistanceToBeamXYConverter:
    when(DetectorDistanceToBeamXYConverter).parse_table().thenReturn(
        LOOKUP_TABLE_TEST_VALUES
    )
    return DetectorDistanceToBeamXYConverter("test.txt")


@pytest.mark.parametrize(
    "detector_distance, axis, expected_value",
    [
        (100.0, Axis.Y_AXIS, 160.0),
        (200.0, Axis.X_AXIS, 151.0),
        (150.0, Axis.X_AXIS, 150.5),
        (190.0, Axis.Y_AXIS, 164.5),
    ],
)
def test_interpolate_beam_xy_from_det_distance(
    fake_converter: DetectorDistanceToBeamXYConverter,
    detector_distance: float,
    axis: Axis,
    expected_value: float,
):
    assert (
        type(fake_converter.get_beam_xy_from_det_dist(detector_distance, axis)) == float
    )

    assert (
        fake_converter.get_beam_xy_from_det_dist(detector_distance, axis)
        == expected_value
    )


def test_get_beam_in_pixels(fake_converter: DetectorDistanceToBeamXYConverter):
    detector_distance = 100.0
    image_size_pixels = 100
    detector_dimensions = 200.0
    interpolated_x_value = 150.0
    interpolated_y_value = 160.0

    when(fake_converter).get_beam_xy_from_det_dist(100.0, Axis.Y_AXIS).thenReturn(
        interpolated_y_value
    )
    when(fake_converter).get_beam_xy_from_det_dist(100.0, Axis.X_AXIS).thenReturn(
        interpolated_x_value
    )
    expected_y_value = interpolated_y_value * image_size_pixels / detector_dimensions
    expected_x_value = interpolated_x_value * image_size_pixels / detector_dimensions

    calculated_y_value = fake_converter.get_beam_y_pixels(
        detector_distance, image_size_pixels, detector_dimensions
    )

    assert calculated_y_value == expected_y_value
    assert (
        fake_converter.get_beam_x_pixels(
            detector_distance, image_size_pixels, detector_dimensions
        )
        == expected_x_value
    )


def test_parse_table():
    test_file = "src/artemis/devices/unit_tests/test_lookup_table.txt"
    test_converter = DetectorDistanceToBeamXYConverter(test_file)

    assert test_converter.lookup_file == test_file
    assert test_converter.lookup_table_values == LOOKUP_TABLE_TEST_VALUES

    test_converter.reload_lookup_table()

    assert test_converter.lookup_file == test_file
    assert test_converter.lookup_table_values == LOOKUP_TABLE_TEST_VALUES
