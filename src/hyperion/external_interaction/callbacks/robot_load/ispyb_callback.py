from __future__ import annotations

from event_model.documents.run_start import RunStart
from event_model.documents.run_stop import RunStop

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.ispyb.ispyb_utils import get_ispyb_config
from hyperion.external_interaction.ispyb.store_robot_action_in_ispyb import (
    StoreRobotLoadInIspyb,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import ROBOT_LOAD_PLAN
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)


class RobotLoadISPyBCallback(PlanReactiveCallback):
    """Callback class to handle the deposition of robot load into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_reading_hardware' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = RobotLoadISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks
    """

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == ROBOT_LOAD_PLAN:
            self.uid_to_finalize_on = doc.get("uid")
            ISPYB_LOGGER.info("ISPyB robot load deposition started.")
            json_params = doc.get("hyperion_internal_parameters")
            params = WaitForRobotLoadThenCentreInternalParameters.from_json(json_params)
            self.ispyb: StoreRobotLoadInIspyb = StoreRobotLoadInIspyb(
                get_ispyb_config(), params
            )
            self.ispyb.begin_deposition()

    def activity_gated_stop(self, doc: RunStop):
        if doc.get("run_start") == self.uid_to_finalize_on:
            exit_status = "SUCCESS" if doc.get("exit_status") == "success" else "ERROR"
            reason = doc.get("reason") or "OK"
            self.ispyb.end_deposition(exit_status, reason)
