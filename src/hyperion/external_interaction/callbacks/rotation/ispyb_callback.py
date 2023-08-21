from __future__ import annotations

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.ispyb.store_in_ispyb import StoreRotationInIspyb
from hyperion.log import set_dcgid_tag
from src.hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class RotationISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_readings' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = RotationISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of a RotationCallbackCollection.
    """

    def __init__(self, parameters: GridscanInternalParameters):
        super().__init__(parameters)
        self.ispyb: StoreRotationInIspyb = StoreRotationInIspyb(
            self.ispyb_config, self.params
        )
        self.ispyb_ids: tuple[int, int] | tuple[None, None] = (None, None)

    def append_to_comment(self, comment: str):
        self._append_to_comment(self.ispyb_ids[0], comment)

    def event(self, doc: dict):
        super().event(doc)
        set_dcgid_tag(self.ispyb_ids[1])

    def stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            super().stop(doc)
