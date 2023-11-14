from __future__ import annotations

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import ROTATION_OUTER_PLAN
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


class RotationZocaloCallback(CallbackBase):
    """Simple callback which sends the ISPyB IDs for a rotation data collection to
    zocalo. Both run_start() and run_end() are sent when the collection is done.
    Triggers on the 'stop' document for 'rotation_scan_main'."""

    def __init__(
        self,
        ispyb_handler: RotationISPyBCallback,
    ):
        self.ispyb: RotationISPyBCallback = ispyb_handler
        self.run_uid = None

    def start(self, doc: dict):
        ISPYB_LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == ROTATION_OUTER_PLAN:
            ISPYB_LOGGER.info(
                "Zocalo callback recieved start document with experiment parameters."
            )
            params = RotationInternalParameters.from_json(
                doc.get("hyperion_internal_parameters")
            )
            zocalo_environment = params.hyperion_params.zocalo_environment
            ISPYB_LOGGER.info(f"Zocalo environment set to {zocalo_environment}.")
            self.zocalo_interactor = ZocaloInteractor(zocalo_environment)

        if self.run_uid is None:
            self.run_uid = doc.get("uid")

    def stop(self, doc: dict):
        if self.run_uid and doc.get("run_start") == self.run_uid:
            ISPYB_LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}."
            )
            if self.ispyb.ispyb_ids.data_collection_ids is not None:
                assert isinstance(self.ispyb.ispyb_ids.data_collection_ids, int)
                self.zocalo_interactor.run_start(
                    self.ispyb.ispyb_ids.data_collection_ids
                )
                self.zocalo_interactor.run_end(self.ispyb.ispyb_ids.data_collection_ids)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
