import concurrent.futures
import getpass
import socket
from functools import partial
from time import sleep
from typing import Callable, Dict
from unittest.mock import MagicMock, call, patch

import pytest
from pytest import mark, raises
from zocalo.configuration import Configuration

from artemis.external_interaction.fgs_callback_collection import FGSCallbackCollection
from artemis.external_interaction.ispyb.ispyb_dataclass import Point3D
from artemis.external_interaction.tests.conftest import TestData
from artemis.parameters.constants import SIM_ZOCALO_ENV
from artemis.parameters.internal_parameters import InternalParameters
from artemis.utils import Point3D

EXPECTED_DCID = 100
EXPECTED_RUN_START_MESSAGE = {"event": "start", "ispyb_dcid": EXPECTED_DCID}
EXPECTED_RUN_END_MESSAGE = {
    "event": "end",
    "ispyb_dcid": EXPECTED_DCID,
    "ispyb_wait_for_runstatus": "1",
}

td = TestData()


def test_execution_of_run_gridscan_triggers_zocalo_calls(
    mock_ispyb_update_time_and_status: MagicMock,
    mock_ispyb_get_time: MagicMock,
    mock_ispyb_store_grid_scan: MagicMock,
    nexus_writer: MagicMock,
):

    dc_ids = [1, 2]
    dcg_id = 4

    mock_ispyb_store_grid_scan.return_value = [dc_ids, None, dcg_id]
    mock_ispyb_get_time.return_value = td.DUMMY_TIME_STRING
    mock_ispyb_update_time_and_status.return_value = None

    params = InternalParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.zocalo_handler._wait_for_result = MagicMock()
    callbacks.zocalo_handler._run_end = MagicMock()
    callbacks.zocalo_handler._run_start = MagicMock()

    callbacks.ispyb_handler.start(td.test_start_document)
    callbacks.zocalo_handler.start(td.test_start_document)
    callbacks.ispyb_handler.descriptor(td.test_descriptor_document)
    callbacks.zocalo_handler.descriptor(td.test_descriptor_document)
    callbacks.ispyb_handler.event(td.test_event_document)
    callbacks.zocalo_handler.event(td.test_event_document)
    callbacks.ispyb_handler.stop(td.test_stop_document)
    callbacks.zocalo_handler.stop(td.test_stop_document)

    callbacks.zocalo_handler._run_start.assert_has_calls([call(x) for x in dc_ids])
    assert callbacks.zocalo_handler._run_start.call_count == len(dc_ids)

    callbacks.zocalo_handler._run_end.assert_has_calls([call(x) for x in dc_ids])
    assert callbacks.zocalo_handler._run_end.call_count == len(dc_ids)

    callbacks.zocalo_handler._wait_for_result.assert_not_called()


def test_zocalo_handler_raises_assertionerror_when_ispyb_has_no_descriptor(
    nexus_writer: MagicMock,
):

    params = InternalParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.zocalo_handler._run_start = MagicMock()
    callbacks.zocalo_handler._run_end = MagicMock()
    callbacks.zocalo_handler._wait_for_result = MagicMock()
    callbacks.zocalo_handler.start(td.test_start_document)
    callbacks.zocalo_handler.descriptor(td.test_descriptor_document)
    with pytest.raises(AssertionError):
        callbacks.zocalo_handler.event(td.test_event_document)


def test_zocalo_called_to_wait_on_results_when_communicator_wait_for_results_called():
    params = InternalParameters()
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.zocalo_handler._run_start = MagicMock()
    callbacks.zocalo_handler._run_end = MagicMock()
    callbacks.zocalo_handler._wait_for_result = MagicMock()
    callbacks.ispyb_handler.ispyb_ids = (0, 0, 100)
    expected_centre_grid_coords = Point3D(1, 2, 3)
    callbacks.zocalo_handler._wait_for_result.return_value = expected_centre_grid_coords

    callbacks.zocalo_handler.wait_for_results(Point3D(0, 0, 0))
    callbacks.zocalo_handler._wait_for_result.assert_called_once_with(100)
    expected_centre_motor_coords = (
        params.experiment_params.grid_position_to_motor_position(
            Point3D(
                expected_centre_grid_coords.x - 0.5,
                expected_centre_grid_coords.y - 0.5,
                expected_centre_grid_coords.z - 0.5,
            )
        )
    )
    assert (
        callbacks.zocalo_handler.xray_centre_motor_position
        == expected_centre_motor_coords
    )


@patch("zocalo.configuration.from_file")
@patch("artemis.external_interaction.zocalo_interaction.lookup")
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


callbacks = FGSCallbackCollection.from_params(InternalParameters())


@mark.parametrize(
    "function_to_test,function_wrapper,expected_message",
    [
        (callbacks.zocalo_handler._run_start, normally, EXPECTED_RUN_START_MESSAGE),
        (
            callbacks.zocalo_handler._run_start,
            with_exception,
            EXPECTED_RUN_START_MESSAGE,
        ),
        (callbacks.zocalo_handler._run_end, normally, EXPECTED_RUN_END_MESSAGE),
        (callbacks.zocalo_handler._run_end, with_exception, EXPECTED_RUN_END_MESSAGE),
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
@patch("artemis.external_interaction.zocalo_interaction.lookup")
def test_when_message_recieved_from_zocalo_then_point_returned(
    mock_transport_lookup, mock_from_file, mock_wrap_subscribe
):

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
        future = executor.submit(
            callbacks.zocalo_handler._wait_for_result, datacollection_grid_id
        )

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
    assert return_value == Point3D(*reversed(centre_of_mass_coords))
