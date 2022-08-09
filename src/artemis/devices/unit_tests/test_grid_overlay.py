from unittest.mock import MagicMock, call, patch

import pytest

from artemis.devices.oav.grid_overlay import (
    add_grid_border_overlay_to_image,
    add_grid_overlay_to_image,
)


def _test_expected_calls_to_image_draw_line(mock_image_draw: MagicMock, expected_lines):
    mock_image_draw_line = mock_image_draw.return_value.line
    mock_image_draw_line.assert_has_calls(
        [call(line) for line in expected_lines], any_order=True
    )
    assert mock_image_draw_line.call_count == len(expected_lines)


@pytest.mark.parametrize(
    "top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y, expected_lines",
    [
        (
            5,
            5,
            5,
            5,
            5,
            [
                ((5, 5), (5, 30)),
                ((5, 5), (30, 5)),
                ((5, 30), (30, 30)),
                ((30, 5), (30, 30)),
            ],
        ),
        (
            10,
            10,
            10,
            10,
            10,
            [
                ((10, 10), (10, 110)),
                ((10, 10), (110, 10)),
                ((10, 110), (110, 110)),
                ((110, 10), (110, 110)),
            ],
        ),
    ],
)
@patch("artemis.devices.oav.grid_overlay.ImageDraw.Draw")
def test_add_grid_border_overlay_to_image_makes_correct_calls_to_imagedraw(
    mock_imagedraw: MagicMock,
    top_left_x,
    top_left_y,
    box_width,
    num_boxes_x,
    num_boxes_y,
    expected_lines,
):
    image = MagicMock()
    add_grid_border_overlay_to_image(
        image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
    )
    _test_expected_calls_to_image_draw_line(mock_imagedraw, expected_lines)


@pytest.mark.parametrize(
    "top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y, expected_lines",
    [
        (
            3,
            3,
            3,
            3,
            3,
            [
                ((3, 6), (12, 6)),
                ((6, 3), (6, 12)),
                ((3, 9), (12, 9)),
                ((9, 3), (9, 12)),
            ],
        ),
        (
            4,
            4,
            4,
            4,
            4,
            [
                ((4, 8), (20, 8)),
                ((4, 12), (20, 12)),
                ((4, 16), (20, 16)),
                ((8, 4), (8, 20)),
                ((12, 4), (12, 20)),
                ((16, 4), (16, 20)),
            ],
        ),
    ],
)
@patch("artemis.devices.oav.grid_overlay.ImageDraw.Draw")
def test_add_grid_overlay_to_image_makes_correct_calls_to_imagedraw(
    mock_imagedraw: MagicMock,
    top_left_x,
    top_left_y,
    box_width,
    num_boxes_x,
    num_boxes_y,
    expected_lines,
):
    image = MagicMock()
    add_grid_overlay_to_image(
        image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
    )
    _test_expected_calls_to_image_draw_line(mock_imagedraw, expected_lines)
