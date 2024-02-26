from __future__ import annotations

from typing import TYPE_CHECKING

from dodal.devices.zocalo import (
    ZocaloTrigger,
)

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import ROTATION_PLAN_MAIN

if TYPE_CHECKING:
    from event_model import RunStart, RunStop


class RotationZocaloCallback(PlanReactiveCallback):
    """Simple callback which sends the ISPyB IDs for a rotation data collection to
    zocalo. Both run_start() and run_end() are sent when the collection is done.
    Triggers on the 'stop' document for 'rotation_scan_main'."""

    def __init__(
        self,
        ispyb_handler: RotationISPyBCallback,
    ):
        super().__init__(ISPYB_LOGGER)
        self.ispyb: RotationISPyBCallback = ispyb_handler
        self.run_uid = None

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == ROTATION_PLAN_MAIN:
            self.run_uid = doc.get("uid")
            ISPYB_LOGGER.info(
                "Zocalo callback received start document with experiment parameters."
            )
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)

    def activity_gated_stop(self, doc: RunStop):
        if self.run_uid and doc.get("run_start") == self.run_uid:
            self.run_uid = None
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids.data_collection_ids is not None:
                ISPYB_LOGGER.info(
                    f"Zocalo callback submitting job {self.ispyb.ispyb_ids.data_collection_ids}"
                )
                assert isinstance(self.ispyb.ispyb_ids.data_collection_ids, int)
                self.zocalo_interactor.run_start(
                    self.ispyb.ispyb_ids.data_collection_ids
                )
                self.zocalo_interactor.run_end(self.ispyb.ispyb_ids.data_collection_ids)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
