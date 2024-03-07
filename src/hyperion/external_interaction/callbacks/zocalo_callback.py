from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from bluesky.callbacks import CallbackBase
from dodal.devices.zocalo import (
    ZocaloTrigger,
)

from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import CONST

if TYPE_CHECKING:
    from event_model.documents import RunStart, RunStop


class ZocaloCallback(CallbackBase):
    """Callback class to handle the triggering of Zocalo processing.
    Sends zocalo a run_start signal on receiving a start document for the specified
    sub-plan, and sends a run_end signal on receiving a stop document for the same plan.

    The metadata of the sub-plan this starts on must include a zocalo_environment.

    Shouldn't be subscribed directly to the RunEngine, instead should be passed to the
    `emit` argument of an ISPyB callback which appends DCIDs to the relevant start doc.
    """

    def _reset_state(self):
        self.run_uid: Optional[str] = None
        self.triggering_plan: Optional[str] = None
        self.ispyb_ids: Optional[tuple[int]] = None
        self.zocalo_interactor: Optional[ZocaloTrigger] = None

    def __init__(
        self,
    ):
        super().__init__()
        self._reset_state()

    def start(self, doc: RunStart):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if triggering_plan := doc.get(CONST.TRIGGER.ZOCALO):
            self.triggering_plan = triggering_plan
        if self.triggering_plan and doc.get("subplan_name") == self.triggering_plan:
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)
            self.run_uid = doc.get("uid")
            if (
                isinstance(ispyb_ids := doc.get("ispyb_dcids"), tuple)
                and len(ispyb_ids) > 0
            ):
                self.ispyb_ids = ispyb_ids
                for id in self.ispyb_ids:
                    self.zocalo_interactor.run_start(id)
            else:
                raise ISPyBDepositionNotMade(
                    f"No ISPyB IDs received by the start of {self.triggering_plan=}"
                )

    def stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb_ids and self.zocalo_interactor:
                for id in self.ispyb_ids:
                    self.zocalo_interactor.run_end(id)
            self._reset_state()
