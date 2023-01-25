import concurrent.futures
import getpass
import socket
from functools import partial
from time import sleep
from typing import Callable, Dict
from unittest.mock import MagicMock, patch

from pytest import mark, raises
from zocalo.configuration import Configuration

from artemis.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from artemis.parameters.constants import SIM_ZOCALO_ENV
from artemis.utils import Point3D

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}


@patch("zocalo.configuration.from_file")
@patch("artemis.external_interaction.zocalo.zocalo_interaction.lookup")
def _test_zocalo(
    func_testing: Callable, expected_params: dict, mock_transport_lookup, mock_from_file
):
    mock_zc = MagicMock()
    mock_from_file.return_value = mock_zc
    mock_transport = MagicMock()
    mock_transport_lookup.return_value = MagicMock()
    mock_transport_lookup.return_value.return_value = mock_transport

    func_testing(mock_transport)

    mock_zc.activate_environment.assert_called_once_with(SIM_ZOCALO_ENV)
    mock_transport.connect.assert_called_once()
    expected_message = {
        "recipes": ["mimas"],
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


zc = ZocaloInteractor(environment=SIM_ZOCALO_ENV)


@mark.parametrize(
    "function_to_test,function_wrapper,expected_message",
    [
        (zc.run_start, normally, EXPECTED_RUN_START_MESSAGE),
        (
            zc.run_start,
            with_exception,
            EXPECTED_RUN_START_MESSAGE,
        ),
        (zc.run_end, normally, EXPECTED_RUN_END_MESSAGE),
        (zc.run_end, with_exception, EXPECTED_RUN_END_MESSAGE),
    ],
)
def test__run_start_and_end(
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


@patch("workflows.recipe.wrap_subscribe")
@patch("zocalo.configuration.from_file")
@patch("artemis.external_interaction.zocalo.zocalo_interaction.lookup")
def test_when_message_recieved_from_zocalo_then_point_returned(
    mock_transport_lookup, mock_from_file, mock_wrap_subscribe
):
    zc = ZocaloInteractor(environment=SIM_ZOCALO_ENV)
    centre_of_mass_coords = [2.942925659754348, 7.142683401382778, 6.79110544979448]

    message = [
        {
            "max_voxel": [3, 5, 5],
            "centre_of_mass": centre_of_mass_coords,
        }
    ]
    datacollection_grid_id = 7263143
    step_params = {"dcid": "8183741", "dcgid": str(datacollection_grid_id)}

    mock_zc: Configuration = MagicMock()
    mock_from_file.return_value = mock_zc
    mock_transport = MagicMock()
    mock_transport_lookup.return_value = MagicMock()
    mock_transport_lookup.return_value.return_value = mock_transport

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(zc.wait_for_result, datacollection_grid_id)

        for _ in range(10):
            sleep(0.1)
            if mock_wrap_subscribe.call_args:
                break

        result_func = mock_wrap_subscribe.call_args[0][2]

        mock_recipe_wrapper = MagicMock()
        mock_recipe_wrapper.recipe_step.__getitem__.return_value = step_params
        result_func(mock_recipe_wrapper, {}, message)

        return_value = future.result()

    assert type(return_value) == Point3D
    assert return_value == Point3D(*centre_of_mass_coords)
