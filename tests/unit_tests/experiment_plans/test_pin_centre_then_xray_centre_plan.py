from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.devices.detector_motion import ShutterState
from dodal.devices.oav.oav_detector import OAVConfigParams

from hyperion.experiment_plans.pin_centre_then_xray_centre_plan import (
    create_parameters_for_grid_detection,
    pin_centre_then_xray_centre_plan,
    pin_tip_centre_then_xray_centre,
)
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectParams,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)

from .conftest import (
    add_simple_oav_mxsc_callback_handlers,
    add_simple_pin_tip_centre_handlers,
)


@pytest.fixture
def test_pin_centre_then_xray_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_pin_centre_then_xray_centre_parameters.json"
    )
    return PinCentreThenXrayCentreInternalParameters(**params)


def test_when_create_parameters_for_grid_detection_then_parameters_created(
    test_pin_centre_then_xray_centre_params: PinCentreThenXrayCentreInternalParameters,
):
    grid_detect_params = create_parameters_for_grid_detection(
        test_pin_centre_then_xray_centre_params
    )

    assert isinstance(
        grid_detect_params.experiment_params, GridScanWithEdgeDetectParams
    )
    assert grid_detect_params.experiment_params.exposure_time == 0.1


@patch(
    "hyperion.experiment_plans.pin_centre_then_xray_centre_plan.pin_tip_centre_plan",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.pin_centre_then_xray_centre_plan.detect_grid_and_do_gridscan",
    autospec=True,
)
def test_when_pin_centre_xray_centre_called_then_plan_runs_correctly(
    mock_detect_and_do_gridscan: MagicMock,
    mock_pin_tip_centre: MagicMock,
    test_pin_centre_then_xray_centre_params: PinCentreThenXrayCentreInternalParameters,
    test_config_files,
):
    RE = RunEngine()
    RE(
        pin_centre_then_xray_centre_plan(
            MagicMock(), test_pin_centre_then_xray_centre_params, test_config_files
        )
    )

    mock_detect_and_do_gridscan.assert_called_once()
    mock_pin_tip_centre.assert_called_once()


@patch(
    "hyperion.experiment_plans.pin_centre_then_xray_centre_plan.pin_tip_centre_plan",
    autospec=True,
)
@patch(
    "hyperion.external_interaction.callbacks.xray_centre.zocalo_callback.XrayCentreZocaloCallback.wait_for_results",
    lambda _, __: ([0, 0, 0], [1, 1, 1]),
)
def test_when_pin_centre_xray_centre_called_then_detector_positioned(
    mock_pin_tip_centre: MagicMock,
    test_pin_centre_then_xray_centre_params: PinCentreThenXrayCentreInternalParameters,
    simple_beamline,
    test_config_files,
    sim,
):
    simple_beamline.oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    simple_beamline.oav.parameters.micronsPerXPixel = 0.806
    simple_beamline.oav.parameters.micronsPerYPixel = 0.806
    simple_beamline.oav.parameters.beam_centre_i = 549
    simple_beamline.oav.parameters.beam_centre_j = 347

    sim = RunEngineSimulator()
    sim.add_handler_for_callback_subscribes()
    add_simple_pin_tip_centre_handlers(sim)
    add_simple_oav_mxsc_callback_handlers(sim)

    def add_handlers_to_simulate_detector_motion(msg: Msg):
        sim.add_handler(
            "read",
            "detector_motion_shutter",
            lambda msg_: {"values": {"value": int(ShutterState.OPEN)}},
        )
        sim.add_handler(
            "read",
            "detector_motion_z_motor_done_move",
            lambda msg_: {"values": {"value": 1}},
        )

    sim.add_wait_handler(
        add_handlers_to_simulate_detector_motion, "ready_for_data_collection"
    )

    messages = sim.simulate_plan(
        pin_tip_centre_then_xray_centre(
            simple_beamline,
            test_pin_centre_then_xray_centre_params,
            test_config_files["oav_config_json"],
        )
    )

    messages = sim.assert_message_and_return_remaining(
        messages, lambda msg: msg.obj is simple_beamline.detector_motion.z
    )
    assert messages[0].args[0] == 100
    assert messages[0].kwargs["group"] == "ready_for_data_collection"
    assert messages[1].obj is simple_beamline.detector_motion.shutter
    assert messages[1].args[0] == 1
    assert messages[1].kwargs["group"] == "ready_for_data_collection"
    messages = sim.assert_message_and_return_remaining(
        messages[2:],
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == "ready_for_data_collection",
    )
    sim.assert_message_and_return_remaining(
        messages[2:],
        lambda msg: msg.command == "open_run"
        and msg.kwargs["subplan_name"] == "do_fgs",
    )
