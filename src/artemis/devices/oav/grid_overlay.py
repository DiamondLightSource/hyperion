from pathlib import Path

import bluesky.plan_stubs as bps
from bluesky import RunEngine
from ophyd import Component, Signal
from PIL import Image, ImageDraw

from src.artemis.devices.oav import OAV, Snapshot


def add_outer_overlay(
    image: Image.Image,
    top_left_x: int,
    top_left_y: int,
    box_width: int,
    num_boxes_x: int,
    num_boxes_y: int,
):
    draw = ImageDraw.Draw(image)
    top_left = (top_left_x, top_left_y)
    top_right = (top_left_x + box_width * num_boxes_x, top_left_y)
    bottom_left = (top_left_x, top_left_y + num_boxes_y * box_width)
    bottom_right = (
        top_left_x + box_width * num_boxes_x,
        top_left_y + num_boxes_y * box_width,
    )
    top = (top_left, top_right)
    left = (top_left, bottom_left)
    right = (top_right, bottom_right)
    bottom = (bottom_left, bottom_right)
    for line in [top, left, right, bottom]:
        draw.line(line)


def add_grid_overlay(
    image: Image.Image,
    top_left_x: int,
    top_left_y: int,
    box_width: int,
    num_boxes_x: int,
    num_boxes_y: int,
):
    draw = ImageDraw.Draw(image)
    for i in range(1, num_boxes_x):
        top = (top_left_x + i * box_width, top_left_y)
        bottom = (top_left_x + i * box_width, top_left_y + num_boxes_y * box_width)
        line = (top, bottom)
        draw.line(line)
    for i in range(1, num_boxes_y):
        left = (top_left_x, top_left_y + i * box_width)
        right = (top_left_x + num_boxes_x * box_width, top_left_y + i * box_width)
        line = (left, right)
        draw.line(line)


def add_full_overlay(
    image: Image.Image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
):
    add_outer_overlay(
        image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
    )
    add_grid_overlay(image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y)


class SnapshotWithGrid(Snapshot):
    top_left_x_signal: Signal = Component(Signal)
    top_left_y_signal: Signal = Component(Signal)
    box_width_signal: Signal = Component(Signal)
    num_boxes_x_signal: Signal = Component(Signal)
    num_boxes_y_signal: Signal = Component(Signal)

    def post_processing(self, image: Image.Image):
        top_left_x = self.top_left_x_signal.get()
        top_left_y = self.top_left_y_signal.get()
        box_width = self.box_width_signal.get()
        num_boxes_x = self.num_boxes_x_signal.get()
        num_boxes_y = self.num_boxes_y_signal.get()
        filename_str = self.filename.get()
        directory_str = self.directory.get()
        add_outer_overlay(
            image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
        )
        outer_overlay_path = Path(f"{directory_str}{filename_str}_outer_overlay.png")
        image.save(outer_overlay_path)
        add_grid_overlay(
            image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
        )
        grid_overlay_path = Path(f"{directory_str}{filename_str}_grid_overlay.png")
        image.save(grid_overlay_path)


def take_snapshot(oav: OAV, snapshot_filename, snapshot_directory):
    oav.wait_for_connection()
    yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
    yield from bps.abs_set(oav.snapshot.directory, snapshot_directory)
    yield from bps.trigger(oav.snapshot, wait=True)


if __name__ == "__main__":
    beamline = "BL03I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01")
    snapshot_filename = "snapshot"
    snapshot_directory = "."
    RE = RunEngine()
    RE(take_snapshot(oav, snapshot_filename, snapshot_directory))
