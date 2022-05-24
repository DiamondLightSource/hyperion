import getpass
import socket
from time import sleep

import workflows.recipe
import workflows.transport
import zocalo.configuration
from src.artemis.ispyb.ispyb_dataclass import Point3D
from workflows.transport import lookup

TIMEOUT = 30


def _get_zocalo_connection():
    zc = zocalo.configuration.from_file()
    zc.activate()

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
    Assumes that appropriate data has already been put into ISpyB

    Args:
        data_collection_id (int): The ID of the data collection representing the gridscan in ISpyB
    """
    _send_to_zocalo({"event": "start", "ispyb_dcid": data_collection_id})


def run_end(data_collection_id: int):
    """Tells the data analysis pipeline we have finished a grid scan.
    Assumes that appropriate data has already been put into ISpyB

    Args:
        data_collection_id (int): The ID of the data collection representing the gridscan in ISpyB
    """
    _send_to_zocalo(
        {
            "event": "end",
            "ispyb_wait_for_runstatus": "1",
            "ispyb_dcid": data_collection_id,
        }
    )


def wait_for_result(data_collection_id: int, timeout: int = TIMEOUT) -> Point3D:
    """Block until a result is recieved from Zocalo.
    Args:
        data_collection_id (int): The ID of the data collection representing the gridscan in ISpyB
        timeout (float): The time in seconds to wait for the result to be recieved.
    Returns:
        Point in grid co-ordinates that is the centre point to move to
    """
    transport = _get_zocalo_connection()
    result_recieved = None

    def receive_result(
        rw: workflows.recipe.RecipeWrapper, header: dict, message: dict
    ) -> None:
        print(f"Received {message}")
        recipe_parameters = rw.recipe_step["parameters"]
        print(f"Recipe step parameters: {recipe_parameters}")
        if recipe_parameters["dcid"] == str(data_collection_id):
            transport.ack(header)
            nonlocal result_recieved
            result_recieved = Point3D(*message["max_voxel"])
        else:
            print(
                f"Warning: results for {recipe_parameters['dcid']} recieved but expected {data_collection_id}"
            )

    workflows.recipe.wrap_subscribe(
        transport,
        "xrc.i03",
        receive_result,
        acknowledgement=True,
        allow_non_recipe_messages=True,
    )

    try:
        for _ in range(timeout):
            sleep(1)
            if result_recieved:
                return result_recieved
        raise TimeoutError(f"Result not received in {timeout} seconds")
    finally:
        transport.disconnect()
