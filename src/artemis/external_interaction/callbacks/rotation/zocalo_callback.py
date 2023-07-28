from __future__ import annotations

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBHandlerCallback,
)
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from artemis.log import LOGGER


class RotationZocaloCallback(CallbackBase):
    def __init__(
        self,
        zocalo_environment: str,
        ispyb_handler: RotationISPyBHandlerCallback,
    ):
        self.ispyb: RotationISPyBHandlerCallback = ispyb_handler
        self.zocalo_interactor = ZocaloInteractor(zocalo_environment)

    def start(self, doc: dict):
        LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == "rotation_scan_main":
            self.run_uid = doc.get("uid")
            if self.ispyb.ispyb_ids[0] is not None:
                self.zocalo_interactor.run_start(self.ispyb.ispyb_ids[0])
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def stop(self, doc: dict):
        if doc.get("run_start") == self.run_uid:
            LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids[0] is not None:
                self.zocalo_interactor.run_end(self.ispyb.ispyb_ids[0])
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
