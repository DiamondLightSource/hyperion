from unittest.mock import patch, MagicMock
from src.artemis.zocalo_interaction import run_start, run_end
from zocalo.configuration import Configuration
from workflows.transport import default_transport
import getpass
import socket
from typing import Callable
from functools import partial


def _test_zocalo(func_testing: Callable, expected_params: dict):
    mock_zc: Configuration = MagicMock()
    mock_transport = MagicMock()
    with patch("zocalo.configuration.from_file", return_value=mock_zc):
        with patch("src.artemis.zocalo_interaction.lookup") as mock_transport_lookup:
            mock_transport_lookup.return_value = MagicMock()
            mock_transport_lookup.return_value.return_value = mock_transport

            func_testing()

            mock_zc.activate.assert_called_once()
            mock_transport_lookup.assert_called_once_with(default_transport)
            mock_transport.connect.assert_called_once()
            expected_message = {
                "recipes": "mimas",
                "parameters": expected_params,
            }

            expected_headers = {
                "zocalo.go.user": getpass.getuser(),
                "zocalo.go.host": socket.gethostname(),
            }
            mock_transport.send.assert_called_once_with(
                "processing_recipe", expected_message, headers=expected_headers
            )


def test_run_start():
    expected_dcid = 100
    expected_message = {"event": "start", "ispyb_dcid": expected_dcid}
    _test_zocalo(partial(run_start, expected_dcid), expected_message)


def test_run_end():
    expected_dcid = 100
    expected_message = {
        "event": "end",
        "ispyb_dcid": expected_dcid,
        "ispyb_wait_for_runstatus": "1",
    }
    _test_zocalo(partial(run_end, expected_dcid), expected_message)
