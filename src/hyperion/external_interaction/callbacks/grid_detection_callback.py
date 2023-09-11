import numpy as np
from bluesky.callbacks import CallbackBase
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_parameters import OAVParameters

from hyperion.device_setup_plans.setup_oav import calculate_x_y_z_of_pixel
from hyperion.log import LOGGER


class GridDetectionCallback(CallbackBase):
    def __init__(
        self, oav_params: OAVParameters, out_parameters: GridScanParams, *args
    ) -> None:
        super().__init__(*args)
        self.x_of_centre_of_first_box_px: float = 0
        self.y_of_centre_of_first_box_px: float = 0
        self.oav_params = oav_params
        self.out_parameters = out_parameters
        self.start_positions: list = []
        self.box_numbers: list = []

        self.micronsPerXPixel = oav_params.micronsPerXPixel
        self.micronsPerYPixel = oav_params.micronsPerYPixel

        self.x_start: float = 0
        self.y1_start: float = 0
        self.y2_start: float = 0
        self.z1_start: float = 0
        self.z2_start: float = 0

        self.x_steps: float = 0
        self.y_steps: float = 0
        self.z_steps: float = 0

        self.x_step_size_mm: float = 0
        self.y_step_size_mm: float = 0
        self.z_step_size_mm: float = 0

        self.box_size_um: float = 0

    def event(self, doc):
        data = doc.get("data")
        top_left_x_px = data["oav_snapshot_top_left_x"]
        box_width_px = data["oav_snapshot_box_width"]
        self.x_of_centre_of_first_box_px = top_left_x_px + box_width_px / 2

        top_left_y_px = data["oav_snapshot_top_left_y"]
        self.y_of_centre_of_first_box_px = top_left_y_px + box_width_px / 2

        smargon_x = data["smargon_x"]
        smargon_y = data["smargon_y"]
        smargon_z = data["smargon_z"]
        smargon_omega = data["smargon_omega"]

        current_xyz = np.array([smargon_x, smargon_y, smargon_z])

        centre_of_first_box = (
            self.x_of_centre_of_first_box_px,
            self.y_of_centre_of_first_box_px,
        )

        position_grid_start = calculate_x_y_z_of_pixel(
            current_xyz, smargon_omega, centre_of_first_box, self.oav_params
        )

        LOGGER.info(f"Calculated start position {position_grid_start}")

        self.start_positions.append(position_grid_start)
        self.box_numbers.append(
            (data["oav_snapshot_num_boxes_x"], data["oav_snapshot_num_boxes_y"])
        )

        self.x_step_size_mm = box_width_px * self.oav_params.micronsPerXPixel / 1000
        self.y_step_size_mm = box_width_px * self.oav_params.micronsPerYPixel / 1000
        self.z_step_size_mm = box_width_px * self.oav_params.micronsPerYPixel / 1000

    def get_grid_parameters(self) -> GridScanParams:
        return GridScanParams(
            x_start=self.start_positions[0][0],
            y1_start=self.start_positions[0][1],
            y2_start=self.start_positions[0][1],
            z1_start=self.start_positions[1][2],
            z2_start=self.start_positions[1][2],
            x_steps=self.box_numbers[0][0],
            y_steps=self.box_numbers[0][1],
            z_steps=self.box_numbers[1][1],
            x_step_size=self.x_step_size_mm,
            y_step_size=self.y_step_size_mm,
            z_step_size=self.z_step_size_mm,
        )
