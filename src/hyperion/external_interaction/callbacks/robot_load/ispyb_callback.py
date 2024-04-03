from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.ispyb.exp_eye_store import end_load, start_load
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import CONST

if TYPE_CHECKING:
    from event_model.documents import EventDescriptor, RunStart, RunStop


class RobotLoadISPyBCallback(PlanReactiveCallback):
    def __init__(self) -> None:
        ISPYB_LOGGER.debug("Initialising ISPyB Robot Load Callback")
        super().__init__(log=ISPYB_LOGGER)
        self.descriptors: Dict[str, EventDescriptor] = {}

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.ROBOT_LOAD:
            assert isinstance(metadata := doc.get("metadata"), Dict)
            start_load(
                metadata["sample_id"], metadata["sample_puck"], metadata["sample_pin"]
            )
        return super().activity_gated_start(doc)

    def activity_gated_stop(self, doc: RunStop) -> RunStop | None:
        ISPYB_LOGGER.debug("ISPyB handler received stop document.")
        exit_status = (
            doc.get("exit_status") or "Exit status not available in stop document!"
        )
        reason = doc.get("reason") or ""
        end_load(exit_status, reason)
        return super().activity_gated_stop(doc)
