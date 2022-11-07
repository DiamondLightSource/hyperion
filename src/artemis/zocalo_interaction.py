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


def _get_zocalo_connection():
    zc = zocalo.configuration.from_file()
    zc.activate_environment("artemis")

    transport = lookup("PikaTransport")()
    transport.connect()

    return transport


def _send_to_zocalo(parameters: dict):
    transport = _get_zocalo_connection()

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


def run_start(data_collection_id: int):
    """Tells the data analysis pipeline we have started a grid scan.
    Assumes that appropriate data has already been put into ISPyB

    Args:
        data_collection_id (int): The ID of the data collection representing the
                                  gridscan in ISPyB
    """
    artemis.log.LOGGER.info(f"Submitting to zocalo with ispyb id {data_collection_id}")
    _send_to_zocalo({"event": "start", "ispyb_dcid": data_collection_id})


def run_end(data_collection_id: int):
    """Tells the data analysis pipeline we have finished a grid scan.
    Assumes that appropriate data has already been put into ISPyB

    Args:
        data_collection_id (int): The ID of the data collection representing the
                                  gridscan in ISPyB

    """
    _send_to_zocalo(
        {
            "event": "end",
            "ispyb_wait_for_runstatus": "1",
            "ispyb_dcid": data_collection_id,
        }
    )


def wait_for_result(data_collection_group_id: int, timeout: int = TIMEOUT) -> Point3D:
    """Block until a result is received from Zocalo.
    Args:
        data_collection_group_id (int): The ID of the data collection group representing
                                        the gridscan in ISPyB

        timeout (float): The time in seconds to wait for the result to be received.
    Returns:
        Point in grid co-ordinates that is the centre point to move to
    """
    transport = _get_zocalo_connection()
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
