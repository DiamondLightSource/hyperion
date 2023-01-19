import os
from typing import Dict

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.ispyb.store_in_ispyb import (
    StoreInIspyb2D,
    StoreInIspyb3D,
)
from artemis.log import LOGGER
from artemis.parameters.constants import ISPYB_PLAN_NAME, SIM_ISPYB_CONFIG
from artemis.parameters.internal_parameters import InternalParameters


class FGSISPyBHandlerCallback(CallbackBase):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self, parameters: InternalParameters):
        self.params = parameters
        self.descriptors: Dict[str, dict] = {}
        ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", SIM_ISPYB_CONFIG)
        if ispyb_config == SIM_ISPYB_CONFIG:
            LOGGER.warning(
                "Using dev ISPyB database. If you want to use the real database, please"
                " set the ISPYB_CONFIG_PATH environment variable."
            )
        self.ispyb = (
            StoreInIspyb3D(ispyb_config, self.params)
            if self.params.experiment_params.is_3d_grid_scan
            else StoreInIspyb2D(ispyb_config, self.params)
        )
        self.ispyb_ids: tuple = (None, None, None)

    def descriptor(self, doc):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: dict):
        LOGGER.debug("ISPyB handler received event document.")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.artemis_params.ispyb_params.undulator_gap = doc["data"][
                "fgs_undulator_gap"
            ]
            self.params.artemis_params.ispyb_params.synchrotron_mode = doc["data"][
                "fgs_synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.artemis_params.ispyb_params.slit_gap_size_x = doc["data"][
                "fgs_slit_gaps_xgap"
            ]
            self.params.artemis_params.ispyb_params.slit_gap_size_y = doc["data"][
                "fgs_slit_gaps_ygap"
            ]

            LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()

    def stop(self, doc: dict):
        LOGGER.debug("ISPyB handler received stop document.")
        exit_status = doc.get("exit_status")
        reason = doc.get("reason")
        if self.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
        self.ispyb.end_deposition(exit_status, reason)
