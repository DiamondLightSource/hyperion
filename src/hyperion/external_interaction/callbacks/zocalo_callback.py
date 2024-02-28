from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from dodal.devices.zocalo import (
    ZocaloTrigger,
)

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER

if TYPE_CHECKING:
    from event_model.documents import RunStart, RunStop


class ZocaloCallback(PlanReactiveCallback):
    """Callback class to handle the triggering of Zocalo processing.
    Sends zocalo a run_start signal on receiving a start document for the specified
    sub-plan, and sends a run_end signal on receiving a stop document for the same plan.

    The metadata of the sub-plan this starts on must include a zocalo_environment.

    Needs to be connected to an ISPyBCallback subscribed to the same run in order
    to have access to the deposition numbers to pass on to Zocalo.
    """

    def __init__(
        self,
        plan_name_to_trigger_on: str,
    ):
        super().__init__(ISPYB_LOGGER)
        self.run_uid: Optional[str] = None
        self.plan_name_to_trigger_on = plan_name_to_trigger_on
        self.ispyb_ids: Optional[tuple[int]] = None

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == self.plan_name_to_trigger_on:
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)
            self.run_uid = doc.get("uid")
            if isinstance(ispyb_ids := doc.get("ispyb_dcids"), tuple):
                self.ispyb_ids = ispyb_ids
                for id in self.ispyb_ids:
                    self.zocalo_interactor.run_start(id)
            else:
                raise ISPyBDepositionNotMade(
                    f"No ISPyB IDs received by the start of {self.plan_name_to_trigger_on=}"
                )

    def activity_gated_stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb_ids:
                for id in self.ispyb_ids:
                    self.zocalo_interactor.run_end(id)
