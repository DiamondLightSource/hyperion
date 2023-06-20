from bluesky.callbacks import CallbackBase


class OavSnapshotCallback(CallbackBase):
    snapshot_filenames: list = []
    out_upper_left: list = []

    def event(self, doc):
        data = doc.get("data")
        self.snapshot_filenames.append(list(data.values())[:3])
        self.out_upper_left.append(list(data.values())[-2:])
