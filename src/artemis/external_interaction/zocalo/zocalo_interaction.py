import getpass
import queue
import socket
from datetime import datetime, timedelta
from time import sleep
from typing import Optional

import workflows.recipe
import workflows.transport
import zocalo.configuration
from numpy import ndarray
from workflows.transport import lookup

import artemis.log
from artemis.exceptions import WarningException

TIMEOUT = 90


class NoDiffractionFound(WarningException):
    pass


class ZocaloInteractor:
    def __init__(self, environment: str = "artemis"):
        self.zocalo_environment: str = environment

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
        """Tells the data analysis pipeline we have started a run.
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
        """Tells the data analysis pipeline we have finished a run.
        Assumes that appropriate data has already been put into ISPyB

        Args:
            data_collection_id (int): The ID of the data collection representing the
                                    gridscan in ISPyB

        """
        self._send_to_zocalo(
            {
                "event": "end",
                "ispyb_dcid": data_collection_id,
            }
        )

    def wait_for_result(
        self, data_collection_group_id: int, timeout: int | None = None
    ) -> ndarray:
        """Block until a result is received from Zocalo.
        Args:
            data_collection_group_id (int): The ID of the data collection group representing
                                            the gridscan in ISPyB

            timeout (float): The time in seconds to wait for the result to be received.
        Returns:
            Returns the message from zocalo, as a list of dicts describing each crystal
            which zocalo found:
            {
                "results": [
                    {
                        "centre_of_mass": [1, 2, 3],
                        "max_voxel": [2, 4, 5],
                        "max_count": 105062,
                        "n_voxels": 35,
                        "total_count": 2387574,
                        "bounding_box": [[1, 2, 3], [3, 4, 4]],
                    },
                    {
                        result 2
                    },
                    ...
                ]
            }
        """
        # Set timeout default like this so that we can modify TIMEOUT during tests
        if timeout is None:
            timeout = TIMEOUT
        transport = self._get_zocalo_connection()
        result_received: queue.Queue = queue.Queue()
        exception: Optional[Exception] = None

        def receive_result(
            rw: workflows.recipe.RecipeWrapper, header: dict, message: dict
        ) -> None:
            try:
                artemis.log.LOGGER.info(f"Received {message}")
                recipe_parameters = rw.recipe_step["parameters"]
                artemis.log.LOGGER.info(f"Recipe step parameters: {recipe_parameters}")
                transport.ack(header)
                received_group_id = recipe_parameters["dcgid"]
                if received_group_id == str(data_collection_group_id):
                    results = message.get("results", [])
                    if len(results) == 0:
                        raise NoDiffractionFound()
                    result_received.put(results)
                else:
                    artemis.log.LOGGER.warning(
                        f"Warning: results for {received_group_id} received but expected \
                            {data_collection_group_id}"
                    )
            except Exception as e:
                nonlocal exception
                exception = e
                raise e

        workflows.recipe.wrap_subscribe(
            transport,
            "xrc.i03",
            receive_result,
            acknowledgement=True,
            allow_non_recipe_messages=False,
        )

        try:
            start_time = datetime.now()
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if result_received.empty():
                    if exception is not None:
                        raise exception
                    else:
                        sleep(0.1)
                else:
                    return result_received.get_nowait()
            raise TimeoutError(
                f"No results returned by Zocalo for dcgid {data_collection_group_id} within timeout of {timeout}"
            )
        finally:
            transport.disconnect()
