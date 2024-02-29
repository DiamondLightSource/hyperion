from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from dodal.devices.zocalo import (
    ZocaloTrigger,
)

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER
from hyperion.utils.utils import number_of_frames_from_scan_spec

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
        ispyb_handler: GridscanISPyBCallback | RotationISPyBCallback,
        plan_name_to_trigger_on: str,
    ):
        super().__init__(ISPYB_LOGGER)
        self.run_uid: Optional[str] = None
        self.ispyb: GridscanISPyBCallback | RotationISPyBCallback = ispyb_handler
        self.plan_name_to_trigger_on = plan_name_to_trigger_on

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == self.plan_name_to_trigger_on:
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)
            self.run_uid = doc.get("uid")

            assert isinstance(scan_points := doc.get("scan_points"), list)
            if self.ispyb.ispyb_ids.data_collection_ids:
                ids_and_shape = list(
                    zip(self.ispyb.ispyb_ids.data_collection_ids, scan_points)
                )
                start_idx = 0
                for id, shape in ids_and_shape:
                    num_frames = number_of_frames_from_scan_spec(shape)
                    self.zocalo_interactor.run_start(
                        id,
                        start_idx,
                        num_frames,
                    )
                    start_idx += num_frames
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def activity_gated_stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids.data_collection_ids:
                for id in self.ispyb.ispyb_ids.data_collection_ids:
                    self.zocalo_interactor.run_end(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
