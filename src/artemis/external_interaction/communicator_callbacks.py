import math
import os
from typing import Dict

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.external_interaction.nexus_writing.write_nexus import (
    NexusWriter,
    create_parameters_for_first_file,
    create_parameters_for_second_file,
)
from artemis.log import LOGGER
from artemis.parameters import ISPYB_PLAN_NAME, SIM_ISPYB_CONFIG, FullParameters


class NexusFileHandlerCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters. Creates the Nexus files on recieving a 'start' document, and updates the
    timestamps on recieving a 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)

    Or decorate a plan using bluesky.preprocessors.subs_decorator.
    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def __init__(self, parameters: FullParameters):
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


class ISPyBHandlerCallback(CallbackBase):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)

    Or decorate a plan using bluesky.preprocessors.subs_decorator.
    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def __init__(self, parameters: FullParameters):
        self.params = parameters
        self.descriptors: Dict[str, dict] = {}
        ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", SIM_ISPYB_CONFIG)
        if ispyb_config == SIM_ISPYB_CONFIG:
            LOGGER.warn(
                "Using dev ISPyB database. If you want to use the real database, please"
                " set the ISPYB_CONFIG_PATH environment variable."
            )
        self.ispyb = (
            StoreInIspyb3D(ispyb_config, self.params)
            if self.params.grid_scan_params.is_3d_grid_scan
            else StoreInIspyb2D(ispyb_config, self.params)
        )
        self.ispyb_ids: tuple = (None, None, None)

    def descriptor(self, doc):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: dict):
        LOGGER.debug(f"\n\nISPyB handler received event document:\n{doc}\n")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.ispyb_params.undulator_gap = doc["data"]["fgs_undulator_gap"]
            self.params.ispyb_params.synchrotron_mode = doc["data"][
                "fgs_synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.ispyb_params.slit_gap_size_x = doc["data"]["fgs_slit_gaps_xgap"]
            self.params.ispyb_params.slit_gap_size_y = doc["data"]["fgs_slit_gaps_ygap"]

            LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()

    def stop(self, doc: dict):
        LOGGER.debug(f"\n\nISPyB handler received stop document:\n\n {doc}\n")
        exit_status = doc.get("exit_status")
        reason = doc.get("reason")
        if self.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
        self.ispyb.end_deposition(exit_status, reason)
