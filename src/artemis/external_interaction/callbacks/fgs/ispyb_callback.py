from __future__ import annotations

import os
from typing import Dict

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.ispyb.store_in_ispyb import (
    Store2DGridscanInIspyb,
    Store3DGridscanInIspyb,
    StoreGridscanInIspyb,
)
from artemis.log import LOGGER, set_dcgid_tag
from artemis.parameters.constants import ISPYB_PLAN_NAME, SIM_ISPYB_CONFIG
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


class FGSISPyBHandlerCallback(CallbackBase):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_readings' event, and updates the
    deposition on recieving it's final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self, parameters: FGSInternalParameters):
        self.params = parameters
        self.descriptors: Dict[str, dict] = {}
        ispyb_config = os.environ.get("ISPYB_CONFIG_PATH", SIM_ISPYB_CONFIG)
        if ispyb_config == SIM_ISPYB_CONFIG:
            LOGGER.warning(
                "Using dev ISPyB database. If you want to use the real database, please"
                " set the ISPYB_CONFIG_PATH environment variable."
            )
        self.ispyb: StoreGridscanInIspyb = (
            Store3DGridscanInIspyb(ispyb_config, self.params)
            if self.params.experiment_params.is_3d_grid_scan
            else Store2DGridscanInIspyb(ispyb_config, self.params)
        )
        self.ispyb_ids: tuple = (None, None, None)
        self.uid_to_finalize_on = None

    def append_to_comment(self, comment: str):
        try:
            for id in self.ispyb_ids[0]:
                self.ispyb.append_to_comment(id, comment)
        except TypeError:
            LOGGER.warning("ISPyB deposition not initialised, can't update comment.")

    def descriptor(self, doc: dict):
        self.descriptors[doc["uid"]] = doc

    def start(self, doc: dict):
        if self.uid_to_finalize_on is None:
            self.uid_to_finalize_on = doc.get("uid")

    def event(self, doc: dict):
        LOGGER.debug("ISPyB handler received event document.")
        event_descriptor = self.descriptors[doc["descriptor"]]

        if event_descriptor.get("name") == ISPYB_PLAN_NAME:
            self.params.artemis_params.ispyb_params.undulator_gap = doc["data"][
                "undulator_gap"
            ]
            self.params.artemis_params.ispyb_params.synchrotron_mode = doc["data"][
                "synchrotron_machine_status_synchrotron_mode"
            ]
            self.params.artemis_params.ispyb_params.slit_gap_size_x = doc["data"][
                "s4_slit_gaps_xgap"
            ]
            self.params.artemis_params.ispyb_params.slit_gap_size_y = doc["data"][
                "s4_slit_gaps_ygap"
            ]
            self.params.artemis_params.ispyb_params.transmission = doc["data"][
                "attenuator_actual_transmission"
            ]

            LOGGER.info("Creating ispyb entry.")
            self.ispyb_ids = self.ispyb.begin_deposition()
            set_dcgid_tag(self.ispyb_ids[2])

    def stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            LOGGER.debug("ISPyB handler received stop document.")
            exit_status = doc.get("exit_status")
            reason = doc.get("reason")
            if self.ispyb_ids == (None, None, None):
                raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
            self.ispyb.end_deposition(exit_status, reason)
            set_dcgid_tag(None)
