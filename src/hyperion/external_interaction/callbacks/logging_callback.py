import json

from bluesky.callbacks import CallbackBase

from hyperion.log import LOGGER


class _BestEffortEncoder(json.JSONEncoder):
    def default(self, o):
        return repr(o)


def _format(doc):
    return json.dumps(doc, indent=2, cls=_BestEffortEncoder)


class VerbosePlanExecutionLoggingCallback(CallbackBase):
    def start(self, doc):
        LOGGER.info(f"START: {_format(doc)}")

    def descriptor(self, doc):
        LOGGER.info(f"DESCRIPTOR: {_format(doc)}")

    def event(self, doc):
        LOGGER.info(f"EVENT: {_format(doc)}")
        return doc

    def stop(self, doc):
        LOGGER.info(f"STOP: {_format(doc)}")
