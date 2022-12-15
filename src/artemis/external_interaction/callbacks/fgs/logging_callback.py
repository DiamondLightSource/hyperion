from bluesky.callbacks import CallbackBase

from artemis.log import LOGGER


class VerbosePlanExecutionLoggingCallback(CallbackBase):
    def __eq__(self, other):
        return isinstance(other, VerbosePlanExecutionLoggingCallback)

    def start(self, doc):
        LOGGER.info(doc)

    def descriptor(self, doc):
        LOGGER.info(doc)

    def event(self, doc):
        LOGGER.info(doc)

    def stop(self, doc):
        LOGGER.info(doc)
