import numpy as np
from bluesky.callbacks import CallbackBase
from dodal.devices.oav.oav_parameters import OAVParameters

from hyperion.device_setup_plans.setup_oav import calculate_x_y_z_of_pixel
from hyperion.log import LOGGER


class GridDetectionCallback(CallbackBase):
    def __init__(self, oav_params: OAVParameters, *args) -> None:
        super().__init__(*args)
        self.x_of_centre_of_first_box_px: float = 0
        self.y_of_centre_of_first_box_px: float = 0
        self.oav_params = oav_params
        self.start_positions: list = []

    def event(self, doc):
        data = doc.get("data")
        top_left_x_px = data["oav_snapshot_top_left_x"]
        grid_width_px = data["oav_snapshot_box_width"]
        self.x_of_centre_of_first_box_px = top_left_x_px + grid_width_px / 2

        top_left_y_px = data["oav_snapshot_top_left_y"]
        self.y_of_centre_of_first_box_px = top_left_y_px + grid_width_px / 2

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
