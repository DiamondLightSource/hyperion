from bluesky.callbacks import CallbackBase

from hyperion.log import LOGGER


class VerbosePlanExecutionLoggingCallback(CallbackBase):
    def start(self, doc):
        LOGGER.info(f"START: {doc}")

    def descriptor(self, doc):
        LOGGER.info(f"DESCRIPTOR: {doc}")

    def event(self, doc):
        LOGGER.info(f"EVENT: {doc}")
        return doc

    def stop(self, doc):
        LOGGER.info(f"STOP: {doc}")
