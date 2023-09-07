from bluesky.callbacks import CallbackBase


class GridDetectionCallback(CallbackBase):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.x_of_centre_of_first_box_px: float = 0

    def event(self, doc):
        data = doc.get("data")
        top_left_x_px = data["oav_snapshot_top_left_x"]
        grid_width_px = data["oav_snapshot_box_width"]
        self.x_of_centre_of_first_box_px = top_left_x_px + grid_width_px / 2
