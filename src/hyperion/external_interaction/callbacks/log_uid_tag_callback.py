from bluesky.callbacks import CallbackBase
from event_model import RunStart, RunStop

from hyperion.log import set_uid_tag


class LogUidTaggingCallback(CallbackBase):
    def __init__(self) -> None:
        """Sets the logging filter to add the outermost run uid to graylog messages"""
        self.run_uid = None

    def start(self, doc: RunStart):
        if self.run_uid is None:
            self.run_uid = doc.get("uid")
            set_uid_tag(self.run_uid)

    def stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            self.run_uid = None
            set_uid_tag(None)
