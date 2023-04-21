from __future__ import annotations

from typing import Optional

from bluesky.callbacks import CallbackBase

from artemis.log import LOGGER
from artemis.parameters.internal_parameters import InternalParameters


class RotationNexusFileHandlerCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters for rotation scans

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    # TODO this is just a placeholder for the collection, registry etc to have something
    # to grab, to be implemented in #370

    def __init__(self, parameters: InternalParameters):
        self.run_uid: Optional[str] = None
        self.params = parameters
        # self.writer = NexusWriter(parameters)

    def start(self, doc: dict):
        LOGGER.info("Setting up nexus files for")

    def stop(self, doc: dict):
        LOGGER.info("Finalising nexus files for")
