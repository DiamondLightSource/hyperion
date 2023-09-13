from bluesky.callbacks import CallbackBase


class OavSnapshotCallback(CallbackBase):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.snapshot_filenames: list = []
        self.out_upper_left: list = []

    def event(self, doc):
        data = doc.get("data")
        self.snapshot_filenames.append(list(data.values())[:3])
        self.out_upper_left.append(
            [data.get("oav_snapshot_top_left_x"), data.get("oav_snapshot_top_left_y")]
        )
