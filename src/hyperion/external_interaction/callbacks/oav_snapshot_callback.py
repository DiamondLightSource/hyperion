from bluesky.callbacks import CallbackBase


class OavSnapshotCallback(CallbackBase):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.snapshot_filenames: list = []
        self.out_upper_left: list = []
        self.box_widths: list = []
        self.no_of_boxes: list = []

    def event(self, doc):
        data = doc.get("data")

        self.snapshot_filenames.append(
            [
                data.get("oav_snapshot_last_saved_path"),
                data.get("oav_snapshot_last_path_outer"),
                data.get("oav.snapshot.last_path_full_overlay"),
            ]
        )

        self.out_upper_left.append(
            [data.get("oav_snapshot_top_left_x"), data.get("oav_snapshot_top_left_y")]
        )

        self.box_widths.append([data.get("oav.snapshot.box_width")])

        self.no_of_boxes.append(
            [data.get("oav.snapshot.num_boxes_x"), data.get("oav.snapshot.num_boxes_y")]
        )
