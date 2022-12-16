from bluesky.callbacks import CallbackBase

from artemis.log import LOGGER


class VerbosePlanExecutionLoggingCallback(CallbackBase):
    def start(self, doc):
        LOGGER.info(doc)

    def descriptor(self, doc):
        LOGGER.info(doc)

    def event(self, doc):
        LOGGER.info(doc)

    def stop(self, doc):
        LOGGER.info(doc)
