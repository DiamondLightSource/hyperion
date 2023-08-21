from __future__ import annotations

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.store_in_ispyb import (
    Store2DGridscanInIspyb,
    Store3DGridscanInIspyb,
    StoreGridscanInIspyb,
)
from hyperion.log import set_dcgid_tag
from hyperion.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


class FGSISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_readings' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = FGSISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self, parameters: FGSInternalParameters):
        super().__init__(parameters)
        self.ispyb: StoreGridscanInIspyb = (
            Store3DGridscanInIspyb(self.ispyb_config, self.params)
            if self.params.experiment_params.is_3d_grid_scan
            else Store2DGridscanInIspyb(self.ispyb_config, self.params)
        )
        self.ispyb_ids: tuple = (None, None, None)

    def append_to_comment(self, comment: str):
        for id in self.ispyb_ids[0]:
            self._append_to_comment(id, comment)

    def event(self, doc: dict):
        super().event(doc)
        set_dcgid_tag(self.ispyb_ids[2])

    def stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            if self.ispyb_ids == (None, None, None):
                raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
            super().stop(doc)
