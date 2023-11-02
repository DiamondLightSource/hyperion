from __future__ import annotations

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.ispyb.store_in_ispyb import StoreRotationInIspyb
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


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

    def __init__(self, parameters: RotationInternalParameters):
        self.params: RotationInternalParameters
        super().__init__(parameters)
        self.ispyb: StoreRotationInIspyb = StoreRotationInIspyb(
            self.ispyb_config, self.params
        )
        self.ispyb_ids: tuple[int, int] | tuple[None, None] = (None, None)

    def append_to_comment(self, comment: str):
        assert self.ispyb_ids[0] is not None
        self._append_to_comment(self.ispyb_ids[0], comment)

    def start(self, doc: dict):
        ISPYB_LOGGER.info("ISPYB handler received start document.")
        if doc.get("subplan_name") == "rotation_scan_main":
            self.uid_to_finalize_on = doc.get("uid")

    def event(self, doc: dict):
        super().event(doc)
        set_dcgid_tag(self.ispyb_ids[1])

    def stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            super().stop(doc)
