import numpy as np
from bluesky.callbacks import CallbackBase
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from event_model.documents import Event

from hyperion.device_setup_plans.setup_oav import calculate_x_y_z_of_pixel
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST


class GridDetectionCallback(CallbackBase):
    def __init__(
        self,
        oav_params: OAVConfigParams,
        exposure_time: float,
        set_stub_offsets: bool,
        run_up_distance_mm: float = CONST.I03.PANDA_RUNUP_DIST_MM,
        *args,
    ) -> None:
        super().__init__(*args)
        self.exposure_time = exposure_time
        self.set_stub_offsets = set_stub_offsets
        self.oav_params = oav_params
        self.run_up_distance_mm: float = run_up_distance_mm
        self.start_positions: list = []
        self.box_numbers: list = []

    def event(self, doc: Event):
        data = doc.get("data")
        top_left_x_px = data["oav_snapshot_top_left_x"]
        box_width_px = data["oav_snapshot_box_width"]
        x_of_centre_of_first_box_px = top_left_x_px + box_width_px / 2

        top_left_y_px = data["oav_snapshot_top_left_y"]
        y_of_centre_of_first_box_px = top_left_y_px + box_width_px / 2

        smargon_omega = data["smargon_omega"]
        current_xyz = np.array(
            [data["smargon_x"], data["smargon_y"], data["smargon_z"]]
        )

        centre_of_first_box = (
            x_of_centre_of_first_box_px,
            y_of_centre_of_first_box_px,
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
        return doc

    def get_grid_parameters(self) -> GridScanParams:
        return GridScanParams(
            dwell_time_ms=self.exposure_time * 1000,
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
            set_stub_offsets=self.set_stub_offsets,
        )

    def get_panda_grid_parameters(self) -> PandAGridScanParams:
        return PandAGridScanParams(
            run_up_distance_mm=self.run_up_distance_mm,
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
            set_stub_offsets=self.set_stub_offsets,
        )
