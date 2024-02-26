from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from dodal.devices.zocalo import (
    ZocaloTrigger,
)

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import DO_FGS

if TYPE_CHECKING:
    from event_model.documents import RunStart, RunStop


class XrayCentreZocaloCallback(PlanReactiveCallback):
    """Callback class to handle the triggering of Zocalo processing.
    Sends zocalo a run_start signal on receiving a start document for the 'do_fgs'
    sub-plan, and sends a run_end signal on receiving a stop document for the#
    'run_gridscan' sub-plan.

    Needs to be connected to an ISPyBCallback subscribed to the same run in order
    to have access to the deposition numbers to pass on to Zocalo.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(
        self,
        ispyb_handler: GridscanISPyBCallback,
    ):
        super().__init__(ISPYB_LOGGER)
        self.do_fgs_uid: Optional[str] = None
        self.ispyb: GridscanISPyBCallback = ispyb_handler

    def activity_gated_start(self, doc: RunStart):
        ISPYB_LOGGER.info("XRC Zocalo handler received start document.")
        if doc.get("subplan_name") == DO_FGS:
            assert isinstance(zocalo_environment := doc.get("zocalo_environment"), str)
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloTrigger(zocalo_environment)
            self.do_fgs_uid = doc.get("uid")
            if self.ispyb.ispyb_ids.data_collection_ids:
                for id in self.ispyb.ispyb_ids.data_collection_ids:
                    self.zocalo_interactor.run_start(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def activity_gated_stop(self, doc: RunStop):
        if doc.get("run_start") == self.do_fgs_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids.data_collection_ids:
                for id in self.ispyb.ispyb_ids.data_collection_ids:
                    self.zocalo_interactor.run_end(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
