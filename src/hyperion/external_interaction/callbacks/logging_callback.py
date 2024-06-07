import json

from bluesky.callbacks import CallbackBase

from hyperion.log import LOGGER


class _BestEffortEncoder(json.JSONEncoder):
    def default(self, o):
        return repr(o)


def format_doc_for_log(doc):
    return json.dumps(doc, indent=2, cls=_BestEffortEncoder)


class VerbosePlanExecutionLoggingCallback(CallbackBase):
    def start(self, doc):
        LOGGER.info(f"START: {format_doc_for_log(doc)}")

    def descriptor(self, doc):
        LOGGER.info(f"DESCRIPTOR: {format_doc_for_log(doc)}")

    def event(self, doc):
        LOGGER.info(f"EVENT: {format_doc_for_log(doc)}")
        return doc

    def stop(self, doc):
        LOGGER.info(f"STOP: {format_doc_for_log(doc)}")
