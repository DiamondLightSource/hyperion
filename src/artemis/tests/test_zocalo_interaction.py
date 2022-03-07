from unittest.mock import patch, MagicMock
from src.artemis.zocalo_interaction import run_start, run_end
from zocalo.configuration import Configuration
from workflows.transport import default_transport
import getpass
import socket
from typing import Callable, Dict
from functools import partial
from pytest import raises, mark

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}


@patch("zocalo.configuration.from_file")
@patch("src.artemis.zocalo_interaction.lookup")
def _test_zocalo(
    func_testing: Callable, expected_params: dict, mock_transport_lookup, mock_from_file
):
    mock_zc: Configuration = MagicMock()
    mock_from_file.return_value = mock_zc
    mock_transport = MagicMock()
    mock_transport_lookup.return_value = MagicMock()
    mock_transport_lookup.return_value.return_value = mock_transport

    func_testing(mock_transport)

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
    mock_transport.disconnect.assert_called_once()


def normally(function_to_run, mock_transport):
    function_to_run()


def with_exception(function_to_run, mock_transport):
    mock_transport.send.side_effect = Exception()

    with raises(Exception):
        function_to_run()


@mark.parametrize(
    "function_to_test,function_wrapper,expected_message",
    [
        (run_start, normally, EXPECTED_RUN_START_MESSAGE),
        (run_start, with_exception, EXPECTED_RUN_START_MESSAGE),
        (run_end, normally, EXPECTED_RUN_END_MESSAGE),
        (run_end, with_exception, EXPECTED_RUN_END_MESSAGE),
    ],
)
def test_run_start_and_end(
    function_to_test: Callable, function_wrapper: Callable, expected_message: Dict
):
    """
    Args:
        function_to_test (Callable): The function to test e.g. start/stop zocalo
        function_wrapper (Callable): A wrapper around the function, used to test for expected exceptions
        expected_message (Dict): The expected dictionary sent to zocalo
    """
    function_to_run = partial(function_to_test, EXPECTED_DCID)
    function_to_run = partial(function_wrapper, function_to_run)
    _test_zocalo(function_to_run, expected_message)
