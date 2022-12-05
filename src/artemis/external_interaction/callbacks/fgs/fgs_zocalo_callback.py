import getpass
import math
import queue
import socket
import time
from typing import Callable

import workflows.recipe
import workflows.transport
import zocalo.configuration
from bluesky.callbacks import CallbackBase
from workflows.transport import lookup

import artemis.log
from artemis.external_interaction.callbacks.fgs.fgs_ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.log import LOGGER
from artemis.parameters import ISPYB_PLAN_NAME, FullParameters
from artemis.utils import Point3D

TIMEOUT = 90


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
    """

    def __init__(
        self, parameters: FullParameters, ispyb_handler: FGSISPyBHandlerCallback
    ):
        self.grid_position_to_motor_position: Callable[
            [Point3D], Point3D
        ] = parameters.grid_scan_params.grid_position_to_motor_position
        self.zocalo_env = parameters.zocalo_environment
        self.processing_start_time = 0.0
        self.processing_time = 0.0
        self.results = None
        self.xray_centre_motor_position = None
        self.ispyb = ispyb_handler

    def event(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received event document:\n\n {doc}\n")
        descriptor = self.ispyb.descriptors.get(doc["descriptor"])
        assert descriptor is not None
        event_name = descriptor.get("name")
        if event_name == ISPYB_PLAN_NAME:
            if self.ispyb.ispyb_ids[0] is not None:
                datacollection_ids = self.ispyb.ispyb_ids[0]
                for id in datacollection_ids:
                    self._run_start(id)
            else:
                raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")

    def stop(self, doc: dict):
        LOGGER.debug(f"\n\nZocalo handler received stop document:\n\n {doc}\n")
        if self.ispyb.ispyb_ids == (None, None, None):
            raise ISPyBDepositionNotMade("ISPyB deposition was not initialised!")
        datacollection_ids = self.ispyb.ispyb_ids[0]
        for id in datacollection_ids:
            self._run_end(id)
        self.processing_start_time = time.time()

    def wait_for_results(self, fallback_xyz: Point3D):
        datacollection_group_id = self.ispyb.ispyb_ids[2]
        raw_results = self._wait_for_result(datacollection_group_id)
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

    def _get_zocalo_connection(self, env: str = "artemis"):
        zc = zocalo.configuration.from_file()
        zc.activate_environment(env)

        transport = lookup("PikaTransport")()
        transport.connect()

        return transport

    def _send_to_zocalo(self, parameters: dict):
        transport = self._get_zocalo_connection(self.zocalo_env)

        try:
            message = {
                "recipes": ["mimas"],
                "parameters": parameters,
            }
            header = {
                "zocalo.go.user": getpass.getuser(),
                "zocalo.go.host": socket.gethostname(),
            }
            transport.send("processing_recipe", message, headers=header)
        finally:
            transport.disconnect()

    def _run_start(self, data_collection_id: int):
        """Tells the data analysis pipeline we have started a grid scan.
        Assumes that appropriate data has already been put into ISPyB

        Args:
            data_collection_id (int): The ID of the data collection representing the
                                    gridscan in ISPyB
        """
        artemis.log.LOGGER.info(
            f"Submitting to zocalo with ispyb id {data_collection_id}"
        )
        self._send_to_zocalo({"event": "start", "ispyb_dcid": data_collection_id})

    def _run_end(self, data_collection_id: int):
        """Tells the data analysis pipeline we have finished a grid scan.
        Assumes that appropriate data has already been put into ISPyB

        Args:
            data_collection_id (int): The ID of the data collection representing the
                                    gridscan in ISPyB

        """
        self._send_to_zocalo(
            {
                "event": "end",
                "ispyb_wait_for_runstatus": "1",
                "ispyb_dcid": data_collection_id,
            }
        )

    def _wait_for_result(
        self, data_collection_group_id: int, timeout: int = TIMEOUT
    ) -> Point3D:
        """Block until a result is received from Zocalo.
        Args:
            data_collection_group_id (int): The ID of the data collection group representing
                                            the gridscan in ISPyB

            timeout (float): The time in seconds to wait for the result to be received.
        Returns:
            Returns the centre of the grid box with the strongest diffraction, i.e.,
            which contains the centre of the crystal and which we want to move to.
        """
        transport = self._get_zocalo_connection(self.zocalo_env)
        result_received: queue.Queue = queue.Queue()

        def receive_result(
            rw: workflows.recipe.RecipeWrapper, header: dict, message: dict
        ) -> None:
            artemis.log.LOGGER.info(f"Received {message}")
            recipe_parameters = rw.recipe_step["parameters"]
            artemis.log.LOGGER.info(f"Recipe step parameters: {recipe_parameters}")
            transport.ack(header)
            received_group_id = recipe_parameters["dcgid"]
            if received_group_id == str(data_collection_group_id):
                result_received.put(Point3D(*reversed(message[0]["centre_of_mass"])))
            else:
                artemis.log.LOGGER.warn(
                    f"Warning: results for {received_group_id} received but expected \
                        {data_collection_group_id}"
                )

        workflows.recipe.wrap_subscribe(
            transport,
            "xrc.i03",
            receive_result,
            acknowledgement=True,
            allow_non_recipe_messages=False,
        )

        try:
            return result_received.get(timeout=timeout)
        finally:
            transport.disconnect()
