import getpass
import socket

import zocalo.configuration
from workflows.transport import default_transport, lookup


def _send_to_zocalo(parameters: dict):
    zc = zocalo.configuration.from_file()
    zc.activate()

    transport = lookup("PikaTransport")()
    transport.connect()
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
