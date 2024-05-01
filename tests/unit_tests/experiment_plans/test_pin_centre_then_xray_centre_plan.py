from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.devices.detector.detector_motion import ShutterState
from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.synchrotron import SynchrotronMode

from hyperion.experiment_plans.pin_centre_then_xray_centre_plan import (
    create_parameters_for_grid_detection,
    pin_centre_then_xray_centre_plan,
    pin_tip_centre_then_xray_centre,
)
from hyperion.parameters.gridscan import PinTipCentreThenXrayCentre

from ...conftest import raw_params_from_file


@pytest.fixture
def test_pin_centre_then_xray_centre_params():
    params = raw_params_from_file(
        "tests/test_data/new_parameter_json_files/good_test_pin_centre_then_xray_centre_parameters.json"
    )
    return PinTipCentreThenXrayCentre(**params)


def test_when_create_parameters_for_grid_detection_then_parameters_created(
    test_pin_centre_then_xray_centre_params: PinTipCentreThenXrayCentre,
):
    grid_detect_params = create_parameters_for_grid_detection(
        test_pin_centre_then_xray_centre_params
    )

    assert grid_detect_params.exposure_time_s == 0.1


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
    test_pin_centre_then_xray_centre_params: PinTipCentreThenXrayCentre,
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
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.GridDetectionCallback",
)
@patch(
    "hyperion.experiment_plans.pin_centre_then_xray_centre_plan.pin_tip_centre_plan",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.grid_detect_then_xray_centre_plan.grid_detection_plan",
    autospec=True,
)
def test_when_pin_centre_xray_centre_called_then_detector_positioned(
    mock_grid_detect: MagicMock,
    mock_pin_tip_centre: MagicMock,
    mock_grid_callback: MagicMock,
    test_pin_centre_then_xray_centre_params: PinTipCentreThenXrayCentre,
    simple_beamline,
    test_config_files,
    sim_run_engine,
):
    mock_grid_callback.return_value.get_grid_parameters.return_value = GridScanParams(
        transmission_fraction=0.01,
        dwell_time_ms=0,
        x_start=0,
        y1_start=0,
        y2_start=0,
        z1_start=0,
        z2_start=0,
        x_steps=10,
        y_steps=10,
        z_steps=10,
        x_step_size=0.1,
        y_step_size=0.1,
        z_step_size=0.1,
        set_stub_offsets=False,
    )

    sim_run_engine.add_handler_for_callback_subscribes()

    sim_run_engine.add_handler(
        "read",
        "synchrotron-synchrotron_mode",
        lambda msg_: {"values": {"value": SynchrotronMode.SHUTDOWN}},
    )

    def add_handlers_to_simulate_detector_motion(msg: Msg):
        sim_run_engine.add_handler(
            "read",
            "detector_motion_shutter",
            lambda msg_: {"values": {"value": int(ShutterState.OPEN)}},
        )
        sim_run_engine.add_handler(
            "read",
            "detector_motion_z_motor_done_move",
            lambda msg_: {"values": {"value": 1}},
        )

    sim_run_engine.add_wait_handler(
        add_handlers_to_simulate_detector_motion, "ready_for_data_collection"
    )

    messages = sim_run_engine.simulate_plan(
        pin_tip_centre_then_xray_centre(
            simple_beamline,
            test_pin_centre_then_xray_centre_params,
            test_config_files["oav_config_json"],
        ),
    )

    messages = sim_run_engine.assert_message_and_return_remaining(
        messages, lambda msg: msg.obj is simple_beamline.detector_motion.z
    )
    assert messages[0].args[0] == 100
    assert messages[0].kwargs["group"] == "ready_for_data_collection"
    assert messages[1].obj is simple_beamline.detector_motion.shutter
    assert messages[1].args[0] == 1
    assert messages[1].kwargs["group"] == "ready_for_data_collection"
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[2:],
        lambda msg: msg.command == "wait"
        and msg.kwargs["group"] == "ready_for_data_collection",
    )
    sim_run_engine.assert_message_and_return_remaining(
        messages[2:],
        lambda msg: msg.command == "open_run"
        and msg.kwargs["subplan_name"] == "do_fgs",
    )
