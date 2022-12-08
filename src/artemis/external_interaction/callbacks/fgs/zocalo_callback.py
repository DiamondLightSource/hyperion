import math
import time
from typing import Callable

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from artemis.log import LOGGER
from artemis.parameters import ISPYB_PLAN_NAME, FullParameters
from artemis.utils import Point3D


class FGSZocaloCallback(CallbackBase):
    """Callback class to handle the triggering of Zocalo processing.
    Listens for 'event' and 'stop' documents.

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
        self.results = None
        self.xray_centre_motor_position = None
        self.ispyb = ispyb_handler
        self.zocalo_interactor = ZocaloInteractor(parameters.zocalo_environment)

    def event(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received event document:\n\n {doc}\n")
        descriptor = self.ispyb.descriptors.get(doc["descriptor"])
        assert descriptor is not None
        event_name = descriptor.get("name")
        if event_name == ISPYB_PLAN_NAME:
            if self.ispyb.ispyb_ids[0] is not None:
                datacollection_ids = self.ispyb.ispyb_ids[0]
                for id in datacollection_ids:
                    self.zocalo_interactor.run_start(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def stop(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received stop document:\n\n {doc}\n")
        if self.ispyb.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
        datacollection_ids = self.ispyb.ispyb_ids[0]
        for id in datacollection_ids:
            self.zocalo_interactor.run_end(id)
        self.processing_start_time = time.time()

    def wait_for_results(self, fallback_xyz: Point3D):
        datacollection_group_id = self.ispyb.ispyb_ids[2]
        raw_results = self.zocalo_interactor.wait_for_result(datacollection_group_id)
        self.processing_time = time.time() - self.processing_start_time
        # _wait_for_result returns the centre of the grid box, but we want the corner
        self.results = Point3D(
            raw_results.x - 0.5, raw_results.y - 0.5, raw_results.z - 0.5
        )
        self.xray_centre_motor_position = self.grid_position_to_motor_position(
            self.results
        )

        # We move back to the centre if results aren't found
        assert self.xray_centre_motor_position is not None
        if math.nan in self.xray_centre_motor_position:
            log_msg = (
                f"Zocalo: No diffraction found, using fallback centre {fallback_xyz}"
            )
            self.xray_centre_motor_position = fallback_xyz
            LOGGER.warn(log_msg)

        LOGGER.info(f"Results recieved from zocalo: {self.xray_centre_motor_position}")
        LOGGER.info(f"Zocalo processing took {self.processing_time}s")
