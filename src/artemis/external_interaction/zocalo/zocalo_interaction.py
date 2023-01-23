import getpass
import queue
import socket

import workflows.recipe
import workflows.transport
import zocalo.configuration
from workflows.transport import lookup

import artemis.log
from artemis.utils import Point3D

TIMEOUT = 90


class ZocaloInteractor:
    zocalo_environment: str = "artemis"

    def __init__(self, environment: str = "artemis"):
        self.zocalo_environment = environment

    def _get_zocalo_connection(self):
        zc = zocalo.configuration.from_file()
        zc.activate_environment(self.zocalo_environment)

        transport = lookup("PikaTransport")()
        transport.connect()

        return transport

    def _send_to_zocalo(self, parameters: dict):
        transport = self._get_zocalo_connection()

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

    def run_start(self, data_collection_id: int):
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

    def run_end(self, data_collection_id: int):
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

    def wait_for_result(
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
        transport = self._get_zocalo_connection()
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
                result_received.put(Point3D(*message[0]["centre_of_mass"]))
            else:
                artemis.log.LOGGER.warning(
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
