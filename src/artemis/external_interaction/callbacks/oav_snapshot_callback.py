from bluesky.callbacks import CallbackBase


class OavSnapshotCallback(CallbackBase):
    snapshot_filenames: list = []

    def event(self, doc):
        data = doc.get("data")
        self.snapshot_filenames.append(list(data.values()))
