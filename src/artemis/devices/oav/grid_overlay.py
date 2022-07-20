from functools import partial
from pathlib import Path

from ophyd import Component, Signal
from PIL import Image, ImageDraw

from src.artemis.devices.oav.snapshot import Snapshot


def _add_parallel_lines_to_image(
    image, start_x, start_y, line_length, spacing, num_lines, orientation=0
):
    lines = [
        (
            (start_x, start_y + i * spacing),
            (start_x + line_length, start_y + i * spacing),
        )
        if orientation == 0
        else (
            (start_x + i * spacing, start_y),
            (start_x + i * spacing, start_y + line_length),
        )
        for i in range(num_lines)
    ]
    draw = ImageDraw.Draw(image)
    for line in lines:
        draw.line(line)


_add_vertical_parallel_lines_to_image = partial(
    _add_parallel_lines_to_image, orientation=1
)


_add_horizontal_parallel_lines_to_image = partial(
    _add_parallel_lines_to_image, orientation=0
)


def add_grid_border_overlay_to_image(
    image: Image.Image,
    top_left_x: int,
    top_left_y: int,
    box_width: int,
    num_boxes_x: int,
    num_boxes_y: int,
):
    _add_vertical_parallel_lines_to_image(
        image,
        start_x=top_left_x,
        start_y=top_left_y,
        line_length=num_boxes_y * box_width,
        spacing=num_boxes_x * box_width,
        num_lines=2,
    )
    _add_horizontal_parallel_lines_to_image(
        image,
        start_x=top_left_x,
        start_y=top_left_y,
        line_length=num_boxes_x * box_width,
        spacing=num_boxes_y * box_width,
        num_lines=2,
    )


def add_grid_overlay_to_image(
    image: Image.Image,
    top_left_x: int,
    top_left_y: int,
    box_width: int,
    num_boxes_x: int,
    num_boxes_y: int,
):
    _add_vertical_parallel_lines_to_image(
        image,
        start_x=top_left_x + box_width,
        start_y=top_left_y,
        line_length=num_boxes_y * box_width,
        spacing=box_width,
        num_lines=num_boxes_x - 1,
    )
    _add_horizontal_parallel_lines_to_image(
        image,
        start_x=top_left_x,
        start_y=top_left_y + box_width,
        line_length=num_boxes_x * box_width,
        spacing=box_width,
        num_lines=num_boxes_y - 1,
    )


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
        add_grid_border_overlay_to_image(
            image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
        )
        outer_overlay_path = Path(f"{directory_str}/{filename_str}_outer_overlay.png")
        image.save(outer_overlay_path)
        add_grid_overlay_to_image(
            image, top_left_x, top_left_y, box_width, num_boxes_x, num_boxes_y
        )
        grid_overlay_path = Path(f"{directory_str}/{filename_str}_grid_overlay.png")
        image.save(grid_overlay_path)
