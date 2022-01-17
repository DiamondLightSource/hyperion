import pytest
from mockito import mock, when
from src.artemis.devices.det_dist_to_beam_converter import DetectorDistanceToBeamXYConverter


LOOKUP_TABLE_TEST_VALUES = [[100.0, 200.0], [150.0, 151.0], [160.0, 165.0]]


def create_fake_beam_converter() -> DetectorDistanceToBeamXYConverter:
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
def test_interpolate_beam_xy_from_det_distance(detector_distance, axis, expected_value):
    axis_index = 1 if axis == 'y' else 2
    test_converter = create_fake_beam_converter()
    assert test_converter.get_beam_xy_from_det_dist_mm(detector_distance, LOOKUP_TABLE_TEST_VALUES[axis_index]) == expected_value