from __future__ import annotations

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from hyperion.log import LOGGER
from hyperion.parameters.constants import ROTATION_OUTER_PLAN


class RotationZocaloCallback(CallbackBase):
    """Simple callback which sends the ISPyB IDs for a rotation data collection to
    zocalo. Both run_start() and run_end() are sent when the collection is done.
    Triggers on the 'stop' document for 'rotation_scan_main'."""

    def __init__(
        self,
        ispyb_handler: RotationISPyBCallback,
    ):
        self.ispyb: RotationISPyBCallback = ispyb_handler
        self.run_uid = None

    def start(self, doc: dict):
        LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == ROTATION_OUTER_PLAN:
            LOGGER.info(
                "Zocalo callback recieved start document with experiment parameters."
            )
            assert (
                self.ispyb.params is not None
            ), "ISPyB handler attached to Zocalo handler did not recieve parameters"
            zocalo_environment = self.ispyb.params.hyperion_params.zocalo_environment
            self.zocalo_interactor = ZocaloInteractor(zocalo_environment)
        if self.run_uid is None:
            self.run_uid = doc.get("uid")

    def stop(self, doc: dict):
        if self.run_uid and doc.get("run_start") == self.run_uid:
            LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids[0] is not None:
                self.zocalo_interactor.run_start(self.ispyb.ispyb_ids[0])
                self.zocalo_interactor.run_end(self.ispyb.ispyb_ids[0])
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
