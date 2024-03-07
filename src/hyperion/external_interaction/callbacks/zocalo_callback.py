from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from bluesky.callbacks import CallbackBase
from dodal.devices.zocalo import ZocaloStartInfo, ZocaloTrigger

from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import TRIGGER_ZOCALO_ON, ZOCALO_READ_HARDWARE_PLAN
from hyperion.utils.utils import number_of_frames_from_scan_spec

if TYPE_CHECKING:
    from event_model.documents import Event, EventDescriptor, RunStart, RunStop


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
        self.zocalo_interactor: Optional[ZocaloTrigger] = None
        self.zocalo_info: list[ZocaloStartInfo] = []
        self.descriptors: Dict[str, EventDescriptor] = {}

    def __init__(
        self,
    ):
        super().__init__()
        self._reset_state()

    def start(self, doc: RunStart):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if triggering_plan := doc.get(TRIGGER_ZOCALO_ON):
            self.triggering_plan = triggering_plan
        if self.triggering_plan and doc.get("subplan_name") == self.triggering_plan:
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)
            self.run_uid = doc.get("uid")
            assert isinstance(scan_points := doc.get("scan_points"), list)
            if (
                isinstance(ispyb_ids := doc.get("ispyb_dcids"), tuple)
                and len(ispyb_ids) > 0
            ):
                ids_and_shape = list(zip(ispyb_ids, scan_points))
                start_idx = 0
                self.zocalo_info = []
                for id, shape in ids_and_shape:
                    num_frames = number_of_frames_from_scan_spec(shape)
                    self.zocalo_info.append(
                        ZocaloStartInfo(id, None, start_idx, num_frames)
                    )
                    start_idx += num_frames
            else:
                raise ISPyBDepositionNotMade(
                    f"No ISPyB IDs received by the start of {self.triggering_plan=}"
                )

    def descriptor(self, doc: EventDescriptor):
        self.descriptors[doc["uid"]] = doc

    def event(self, doc: Event) -> Event:
        event_descriptor = self.descriptors[doc["descriptor"]]
        if event_descriptor.get("name") == ZOCALO_READ_HARDWARE_PLAN:
            filename = doc["data"]["eiger_odin_file_writer_id"]
            for start_info in self.zocalo_info:
                start_info.filename = filename
                assert self.zocalo_interactor is not None
                self.zocalo_interactor.run_start(start_info)
        return doc

    def stop(self, doc: RunStop):
        if doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            assert self.zocalo_interactor is not None
            for info in self.zocalo_info:
                self.zocalo_interactor.run_end(info.ispyb_dcid)
            self._reset_state()
