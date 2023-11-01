from __future__ import annotations

import os
from typing import Dict, Optional

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.ispyb.store_in_ispyb import StoreInIspyb
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag, set_up_callback_logging_handlers
from hyperion.parameters.constants import (
    ISPYB_PLAN_NAME,
    ISPYB_UPDATING_COLLECTION,
    SIM_ISPYB_CONFIG,
)
from hyperion.parameters.internal_parameters import InternalParameters


class BaseISPyBCallback(CallbackBase):
    def __init__(self, parameters: InternalParameters):
        """Subclasses should run super().__init__() with parameters, then set
        self.ispyb to the type of ispyb relevant to the experiment and define the type
        for self.ispyb_ids."""
        if ISPYB_LOGGER.handlers == []:
            set_up_callback_logging_handlers(
                "hyperion_ispyb_callback.txt",
                ISPYB_LOGGER,
                "DEBUG",
                True,  # TODO set dev mode for tests and remove this
            )
        self.ispyb: StoreInIspyb
        self.params = parameters
        self.descriptors: Dict[str, dict] = {}
        self.ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", SIM_ISPYB_CONFIG)
        if self.ispyb_config == SIM_ISPYB_CONFIG:
            ISPYB_LOGGER.warning(
                "Using dev ISPyB database. If you want to use the real database, please"
                " set the ISPYB_CONFIG_PATH environment variable."
            )
        self.uid_to_finalize_on: Optional[str] = None

    def _append_to_comment(self, id: int, comment: str):
        assert isinstance(self.ispyb, StoreInIspyb)
        try:
            self.ispyb.append_to_comment(id, comment)
        except TypeError:
            ISPYB_LOGGER.warning(
                "ISPyB deposition not initialised, can't update comment."
            )

    def descriptor(self, doc: dict):
        self.descriptors[doc["uid"]] = doc

    def start(self, doc: dict):
        if self.uid_to_finalize_on is None:
            self.uid_to_finalize_on = doc.get("uid")

    def event(self, doc: dict):
        """Subclasses should extend this to add a call to set_dcig_tag from
        hyperion.log"""

        ISPYB_LOGGER.debug("ISPyB handler received event document.")
        assert isinstance(
            self.ispyb, StoreInIspyb
        ), "ISPyB deposition can't be initialised!"
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.hyperion_params.ispyb_params.undulator_gap = doc["data"][
                "undulator_gap"
            ]
            self.params.hyperion_params.ispyb_params.synchrotron_mode = doc["data"][
                "synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.hyperion_params.ispyb_params.slit_gap_size_x = doc["data"][
                "s4_slit_gaps_xgap"
            ]
            self.params.hyperion_params.ispyb_params.slit_gap_size_y = doc["data"][
                "s4_slit_gaps_ygap"
            ]

        if event_descriptor.get("name") == ISPYB_UPDATING_COLLECTION:
            self.params.hyperion_params.ispyb_params.transmission_fraction = doc[
                "data"
            ]["attenuator_actual_transmission"]
            self.params.hyperion_params.ispyb_params.flux = doc["data"][
                "flux_flux_reading"
            ]

            ISPYB_LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()
            ISPYB_LOGGER.info(f"Recieved ISPYB IDs: {self.ispyb_ids}")

    def stop(self, doc: dict):
        """Subclasses must check that they are recieving a stop document for the correct
        uid to use this method!"""
        assert isinstance(
            self.ispyb, StoreInIspyb
        ), "ISPyB handler recieved stop document, but deposition object doesn't exist!"
        ISPYB_LOGGER.debug("ISPyB handler received stop document.")
        exit_status = doc.get("exit_status")
        reason = doc.get("reason")
        set_dcgid_tag(None)
        try:
            self.ispyb.end_deposition(exit_status, reason)
        except Exception:
            ISPYB_LOGGER.info(
                f"Failed to finalise ISPyB deposition on stop document: {doc}"
            )
