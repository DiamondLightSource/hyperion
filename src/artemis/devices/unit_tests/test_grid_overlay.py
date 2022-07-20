from unittest.mock import MagicMock, call, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky import RunEngine

from src.artemis.devices.oav import OAV
from src.artemis.devices.oav.grid_overlay import (
    add_grid_border_overlay_to_image,
    add_grid_overlay_to_image,
)

TEST_GRID_TOP_LEFT_X = 100
TEST_GRID_TOP_LEFT_Y = 100
TEST_GRID_BOX_WIDTH = 25
TEST_GRID_NUM_BOXES_X = 5
TEST_GRID_NUM_BOXES_Y = 6


def take_snapshot_with_grid(oav: OAV, snapshot_filename, snapshot_directory):
    oav.wait_for_connection()
    yield from bps.abs_set(oav.snapshot.top_left_x_signal, TEST_GRID_TOP_LEFT_X)
    yield from bps.abs_set(oav.snapshot.top_left_y_signal, TEST_GRID_TOP_LEFT_Y)
    yield from bps.abs_set(oav.snapshot.box_width_signal, TEST_GRID_BOX_WIDTH)
    yield from bps.abs_set(oav.snapshot.num_boxes_x_signal, TEST_GRID_NUM_BOXES_X)
    yield from bps.abs_set(oav.snapshot.num_boxes_y_signal, TEST_GRID_NUM_BOXES_Y)
    yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
    yield from bps.abs_set(oav.snapshot.directory, snapshot_directory)
    yield from bps.trigger(oav.snapshot, wait=True)


@pytest.mark.skip(reason="Don't want to actually take snapshots during testing.")
def test_grid_overlay():
    beamline = "BL03I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01")
    snapshot_filename = "snapshot"
    snapshot_directory = "."
    RE = RunEngine()
    RE(take_snapshot_with_grid(oav, snapshot_filename, snapshot_directory))


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
@patch("src.artemis.devices.oav.grid_overlay.ImageDraw.Draw")
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
    expected_calls = 2 * [call(image)] + [
        call(image).line(line) for line in expected_lines
    ]
    actual_calls = mock_imagedraw.mock_calls
    expected_calls.sort()
    actual_calls.sort()
    assert expected_calls == actual_calls


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
@patch("src.artemis.devices.oav.grid_overlay.ImageDraw.Draw")
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
    expected_calls = 2 * [call(image)] + [
        call(image).line(line) for line in expected_lines
    ]
    actual_calls = mock_imagedraw.mock_calls
    expected_calls.sort()
    actual_calls.sort()
    assert actual_calls == expected_calls
