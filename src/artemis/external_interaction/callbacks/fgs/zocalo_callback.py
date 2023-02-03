import time
from typing import Callable, Optional

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.zocalo.zocalo_interaction import (
    NoDiffractionFound,
    ZocaloInteractor,
)
from artemis.log import LOGGER
from artemis.parameters import FullParameters
from artemis.utils import Point3D


class FGSZocaloCallback(CallbackBase):
    """Callback class to handle the triggering of Zocalo processing.
    Sends zocalo a run_start signal on recieving a start document for the 'do_fgs'
    sub-plan, and sends a run_end signal on recieving a stop document for the#
    'run_gridscan' sub-plan.

    Needs to be connected to an ISPyBHandlerCallback subscribed to the same run in order
    to have access to the deposition numbers to pass on to Zocalo.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(
        self, parameters: FullParameters, ispyb_handler: FGSISPyBHandlerCallback
    ):
        self.grid_position_to_motor_position: Callable[
            [Point3D], Point3D
        ] = parameters.grid_scan_params.grid_position_to_motor_position
        self.processing_start_time = 0.0
        self.processing_time = 0.0
        self.run_gridscan_uid: Optional[str] = None
        self.ispyb = ispyb_handler
        self.zocalo_interactor = ZocaloInteractor(parameters.zocalo_environment)

    def start(self, doc: dict):
        LOGGER.info("Zocalo handler received start document.")
        if doc.get("subplan_name") == "do_fgs":
            self.run_gridscan_uid = doc.get("uid")
            if self.ispyb.ispyb_ids[0] is not None:
                datacollection_ids = self.ispyb.ispyb_ids[0]
                for id in datacollection_ids:
                    self.zocalo_interactor.run_start(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def stop(self, doc: dict):
        if doc.get("run_start") == self.run_gridscan_uid:
            LOGGER.info(
                f"Zocalo handler received stop document, for run {doc.get('run_start')}, and started run = {self.started_run}."
            )
            if self.ispyb.ispyb_ids == (None, None, None):
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
            datacollection_ids = self.ispyb.ispyb_ids[0]
            for id in datacollection_ids:
                self.zocalo_interactor.run_end(id)
            self.processing_start_time = time.time()

    def wait_for_results(self, fallback_xyz: Point3D) -> Point3D:
        """Blocks until a centre has been received from Zocalo

        Args:
            fallback_xyz (Point3D): The position to fallback to if no centre is found

        Returns:
            Point3D: The xray centre position to move to
        """
        datacollection_group_id = self.ispyb.ispyb_ids[2]
        self.processing_time = time.time() - self.processing_start_time
        try:
            raw_results = self.zocalo_interactor.wait_for_result(
                datacollection_group_id
            )

            # _wait_for_result returns the centre of the grid box, but we want the corner
            results = Point3D(
                raw_results.x - 0.5, raw_results.y - 0.5, raw_results.z - 0.5
            )
            xray_centre = self.grid_position_to_motor_position(results)

            LOGGER.info(f"Results recieved from zocalo: {xray_centre}")

        except NoDiffractionFound:
            # We move back to the centre if results aren't found
            log_msg = (
                f"Zocalo: No diffraction found, using fallback centre {fallback_xyz}"
            )
            xray_centre = fallback_xyz
            LOGGER.warn(log_msg)

        self.ispyb.append_to_comment(
            f"Zocalo processing took {self.processing_time:.2f} s"
        )
        LOGGER.info(f"Zocalo processing took {self.processing_time}s")
        return xray_centre
