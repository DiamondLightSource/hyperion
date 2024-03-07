from bluesky.callbacks import CallbackBase
from event_model import RunStart, RunStop

from hyperion.log import run_uid_filter
from hyperion.parameters.constants import SET_LOG_UID_TAG


class LogUidTaggingCallback(CallbackBase):
    def __init__(self) -> None:
        self.run_uid = None

    def start(self, doc: RunStart):
        if doc.get(SET_LOG_UID_TAG):
            self.run_uid = doc.get("uid")
            run_uid_filter.run_uid = self.run_uid

    def stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            self.run_uid = None
            run_uid_filter.run_uid = None
