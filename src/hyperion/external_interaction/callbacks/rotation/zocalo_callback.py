from __future__ import annotations

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from hyperion.log import ISPYB_LOGGER


class RotationZocaloCallback(CallbackBase):
    """Simple callback which sends the ISPyB IDs for a rotation data collection to
    zocalo. Both run_start() and run_end() are sent when the collection is done.
    Triggers on the 'stop' document for 'rotation_scan_main'."""

    def __init__(
        self,
        zocalo_environment: str,
        ispyb_handler: RotationISPyBCallback,
    ):
        self.ispyb: RotationISPyBCallback = ispyb_handler
        self.zocalo_interactor = ZocaloInteractor(zocalo_environment)
        self.run_uid = None

    def start(self, doc: dict):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if self.run_uid is None:
            self.run_uid = doc.get("uid")

    def stop(self, doc: dict):
        if self.run_uid and doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids[0] is not None:
                self.zocalo_interactor.run_start(self.ispyb.ispyb_ids[0])
                self.zocalo_interactor.run_end(self.ispyb.ispyb_ids[0])
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
