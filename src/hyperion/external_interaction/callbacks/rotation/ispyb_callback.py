from __future__ import annotations

from typing import TYPE_CHECKING

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.ispyb.store_datacollection_in_ispyb import (
    IspybIds,
    StoreRotationInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import ROTATION_OUTER_PLAN, ROTATION_PLAN_MAIN
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

if TYPE_CHECKING:
    from event_model.documents.event import Event


class RotationISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_reading_hardware' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = RotationISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of a RotationCallbackCollection.
    """

    def __init__(self) -> None:
        super().__init__()
        self.last_sample_id: str | None = None

    def append_to_comment(self, comment: str):
        assert isinstance(self.ispyb_ids.data_collection_ids, int)
        self._append_to_comment(self.ispyb_ids.data_collection_ids, comment)

    def activity_gated_start(self, doc: dict):
        if doc.get("subplan_name") == ROTATION_OUTER_PLAN:
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.params = RotationInternalParameters.from_json(json_params)
            dcgid = (
                self.ispyb_ids.data_collection_group_id
                if (
                    self.params.hyperion_params.ispyb_params.sample_id
                    == self.last_sample_id
                )
                else None
            )
            self.ispyb: StoreRotationInIspyb = StoreRotationInIspyb(
                self.ispyb_config, self.params, dcgid
            )
            self.last_sample_id = self.params.hyperion_params.ispyb_params.sample_id
        self.ispyb_ids: IspybIds = IspybIds()
        ISPYB_LOGGER.info("ISPYB handler received start document.")
        if doc.get("subplan_name") == ROTATION_PLAN_MAIN:
            self.uid_to_finalize_on = doc.get("uid")

    def activity_gated_event(self, doc: Event):
        super().activity_gated_event(doc)
        set_dcgid_tag(self.ispyb_ids.data_collection_group_id)

    def activity_gated_stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            self.uid_to_finalize_on = None
            super().activity_gated_stop(doc)
