from bluesky.callbacks import CallbackBase

from artemis.external_interaction.nexus.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.log import LOGGER
from artemis.parameters import InternalParameters


class FGSNexusFileHandlerCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters. Creates the Nexus files on recieving a 'start' document, and updates the
    timestamps on recieving a 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self, parameters: InternalParameters):
        self.nxs_writer_1 = NexusWriter(create_parameters_for_first_file(parameters))
        self.nxs_writer_2 = NexusWriter(create_parameters_for_second_file(parameters))

    def start(self, doc: dict):
        LOGGER.debug(f"\n\nReceived start document:\n\n {doc}\n")
        LOGGER.info("Creating Nexus files.")
        self.nxs_writer_1.create_nexus_file()
        self.nxs_writer_2.create_nexus_file()

    def stop(self, doc: dict):
        LOGGER.debug("Updating Nexus file timestamps.")
        self.nxs_writer_1.update_nexus_file_timestamp()
        self.nxs_writer_2.update_nexus_file_timestamp()
