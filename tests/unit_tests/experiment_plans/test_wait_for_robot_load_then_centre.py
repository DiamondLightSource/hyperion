from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon, StubPosition
from dodal.devices.webcam import Webcam
from ophyd.sim import NullStatus, instantiate_fake_device
from ophyd_async.core import set_mock_value

from hyperion.experiment_plans.robot_load_then_centre_plan import (
    RobotLoadThenCentreComposite,
    prepare_for_robot_load,
    robot_load_then_centre,
    take_robot_snapshots,
)
from hyperion.external_interaction.callbacks.robot_load.ispyb_callback import (
    RobotLoadISPyBCallback,
)
from hyperion.parameters.gridscan import PinTipCentreThenXrayCentre, RobotLoadThenCentre

from ...conftest import raw_params_from_file


@pytest.fixture
def robot_load_composite(
    smargon, dcm, robot, aperture_scatterguard, oav, webcam
) -> RobotLoadThenCentreComposite:
    composite: RobotLoadThenCentreComposite = MagicMock()
    composite.smargon = smargon
    composite.dcm = dcm
    set_mock_value(composite.dcm.energy_in_kev.user_readback, 11.105)
    composite.robot = robot
    composite.aperture_scatterguard = aperture_scatterguard
    composite.smargon.stub_offsets.set = MagicMock(return_value=NullStatus())
    composite.aperture_scatterguard.set = MagicMock(return_value=NullStatus())
    composite.oav = oav
    composite.webcam = webcam
    return composite


@pytest.fixture
def robot_load_then_centre_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_robot_load_params.json"
    )
    return RobotLoadThenCentre(**params)


@pytest.fixture
def robot_load_then_centre_params_no_energy(robot_load_then_centre_params):
    robot_load_then_centre_params.demand_energy_ev = None
    return robot_load_then_centre_params


def dummy_set_energy_plan(energy, composite):
    return (yield Msg("set_energy_plan"))


@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_then_centring_plan_run_with_expected_parameters(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
):
    RE = RunEngine()

    RE(robot_load_then_centre(robot_load_composite, robot_load_then_centre_params))
    composite_passed = mock_centring_plan.call_args[0][0]
    params_passed: PinTipCentreThenXrayCentre = mock_centring_plan.call_args[0][1]

    for name, value in vars(composite_passed).items():
        assert value == getattr(robot_load_composite, name)

    assert isinstance(params_passed, PinTipCentreThenXrayCentre)
    assert params_passed.detector_params.expected_energy_ev == 11100


@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(side_effect=dummy_set_energy_plan),
)
def test_when_plan_run_with_requested_energy_specified_energy_change_executes(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    sim_run_engine,
):
    sim_run_engine.add_handler(
        "read",
        "dcm-energy_in_kev",
        lambda msg: {"dcm-energy_in_kev": {"value": 11.105}},
    )
    messages = sim_run_engine.simulate_plan(
        robot_load_then_centre(robot_load_composite, robot_load_then_centre_params)
    )
    sim_run_engine.assert_message_and_return_remaining(
        messages, lambda msg: msg.command == "set_energy_plan"
    )
    params_passed: PinTipCentreThenXrayCentre = mock_centring_plan.call_args[0][1]
    assert params_passed.detector_params.expected_energy_ev == 11100


@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan",
    MagicMock(),
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([Msg("set_energy_plan")])),
)
def test_robot_load_then_centre_doesnt_set_energy_if_not_specified_and_current_energy_set_on_eiger(
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params_no_energy: RobotLoadThenCentre,
    sim_run_engine,
):
    sim_run_engine.add_handler(
        "read",
        "dcm-energy_in_kev",
        lambda msg: {"dcm-energy_in_kev": {"value": 11.105}},
    )
    messages = sim_run_engine.simulate_plan(
        robot_load_then_centre(
            robot_load_composite,
            robot_load_then_centre_params_no_energy,
        )
    )
    assert not any(msg for msg in messages if msg.command == "set_energy_plan")
    det_params = robot_load_composite.eiger.set_detector_parameters.call_args[0][0]
    assert det_params.expected_energy_ev == 11105


def run_simulating_smargon_wait(
    robot_load_then_centre_params,
    robot_load_composite,
    total_disabled_reads,
    sim_run_engine,
):
    robot_load_composite.smargon = instantiate_fake_device(Smargon, name="smargon")
    robot_load_composite.eiger = instantiate_fake_device(EigerDetector, name="eiger")

    num_of_reads = 0

    def return_not_disabled_after_reads(_):
        nonlocal num_of_reads
        num_of_reads += 1
        return {"values": {"value": int(num_of_reads < total_disabled_reads)}}

    sim_run_engine.add_handler(
        "read",
        "dcm-energy_in_kev",
        lambda msg: {"dcm-energy_in_kev": {"value": 11.105}},
    )
    sim_run_engine.add_handler(
        "read",
        "smargon_disabled",
        return_not_disabled_after_reads,
    )

    return sim_run_engine.simulate_plan(
        robot_load_then_centre(robot_load_composite, robot_load_then_centre_params)
    )


@pytest.mark.parametrize("total_disabled_reads", [5, 3, 14])
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_given_smargon_disabled_when_plan_run_then_waits_on_smargon(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    total_disabled_reads: int,
    sim_run_engine,
):
    messages = run_simulating_smargon_wait(
        robot_load_then_centre_params,
        robot_load_composite,
        total_disabled_reads,
        sim_run_engine,
    )

    mock_centring_plan.assert_called_once()

    sleep_messages = filter(lambda msg: msg.command == "sleep", messages)
    read_disabled_messages = filter(
        lambda msg: msg.command == "read" and msg.obj.name == "smargon_disabled",
        messages,
    )

    assert len(list(sleep_messages)) == total_disabled_reads - 1
    assert len(list(read_disabled_messages)) == total_disabled_reads


@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_given_smargon_disabled_for_longer_than_timeout_when_plan_run_then_throws_exception(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    sim_run_engine,
):
    with pytest.raises(TimeoutError):
        run_simulating_smargon_wait(
            robot_load_then_centre_params,
            robot_load_composite,
            1000,
            sim_run_engine,
        )


@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_when_plan_run_then_detector_arm_started_before_wait_on_robot_load(
    mock_centring_plan: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
    sim_run_engine,
):
    messages = run_simulating_smargon_wait(
        robot_load_then_centre_params,
        robot_load_composite,
        1,
        sim_run_engine,
    )

    arm_detector_messages = filter(
        lambda msg: msg.command == "set" and msg.obj.name == "eiger_do_arm",
        messages,
    )
    read_disabled_messages = filter(
        lambda msg: msg.command == "read" and msg.obj.name == "smargon_disabled",
        messages,
    )

    arm_detector_messages = list(arm_detector_messages)
    assert len(arm_detector_messages) == 1

    idx_of_arm_message = messages.index(arm_detector_messages[0])
    idx_of_first_read_disabled_message = messages.index(list(read_disabled_messages)[0])

    assert idx_of_arm_message < idx_of_first_read_disabled_message


def test_when_prepare_for_robot_load_called_then_moves_as_expected(
    robot_load_composite: RobotLoadThenCentreComposite,
):
    smargon = robot_load_composite.smargon
    aperture_scatterguard = robot_load_composite.aperture_scatterguard

    smargon.x.user_readback.sim_put(10)  # type: ignore
    smargon.z.user_readback.sim_put(5)  # type: ignore
    smargon.omega.user_readback.sim_put(90)  # type: ignore

    RE = RunEngine()
    RE(prepare_for_robot_load(robot_load_composite))

    assert smargon.x.user_readback.get() == 0
    assert smargon.z.user_readback.get() == 0
    assert smargon.omega.user_readback.get() == 0

    smargon.stub_offsets.set.assert_called_once_with(StubPosition.RESET_TO_ROBOT_LOAD)  # type: ignore
    aperture_scatterguard.set.assert_called_once_with(AperturePositions.ROBOT_LOAD)  # type: ignore


@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.end_load"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.update_barcode_and_snapshots"
)
@patch(
    "hyperion.external_interaction.callbacks.robot_load.ispyb_callback.ExpeyeInteraction.start_load"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.pin_centre_then_xray_centre_plan"
)
@patch(
    "hyperion.experiment_plans.robot_load_then_centre_plan.set_energy_plan",
    MagicMock(return_value=iter([])),
)
def test_given_ispyb_callback_attached_when_robot_load_then_centre_plan_called_then_ispyb_deposited(
    mock_centring_plan: MagicMock,
    start_load: MagicMock,
    update_barcode_and_snapshots: MagicMock,
    end_load: MagicMock,
    robot_load_composite: RobotLoadThenCentreComposite,
    robot_load_then_centre_params: RobotLoadThenCentre,
):
    robot_load_composite.oav.snapshot.last_saved_path.put("test_oav_snapshot")  # type: ignore
    set_mock_value(robot_load_composite.webcam.last_saved_path, "test_webcam_snapshot")
    robot_load_composite.webcam.trigger = MagicMock(return_value=NullStatus())

    RE = RunEngine()
    RE.subscribe(RobotLoadISPyBCallback())

    action_id = 1098
    start_load.return_value = action_id

    RE(robot_load_then_centre(robot_load_composite, robot_load_then_centre_params))

    start_load.assert_called_once_with("cm31105", 4, 12345, 40, 3)
    update_barcode_and_snapshots.assert_called_once_with(
        action_id, "BARCODE", "test_oav_snapshot", "test_webcam_snapshot"
    )
    end_load.assert_called_once_with(action_id, "success", "")


@patch("hyperion.experiment_plans.robot_load_then_centre_plan.datetime")
async def test_when_take_snapshots_called_then_filename_and_directory_set_and_device_triggered(
    mock_datetime: MagicMock, oav: OAV, webcam: Webcam
):
    TEST_DIRECTORY = "TEST"

    mock_datetime.now.return_value.strftime.return_value = "TIME"

    RE = RunEngine()
    oav.snapshot.trigger = MagicMock(side_effect=oav.snapshot.trigger)
    webcam.trigger = MagicMock(return_value=NullStatus())

    RE(take_robot_snapshots(oav, webcam, Path(TEST_DIRECTORY)))

    oav.snapshot.trigger.assert_called_once()
    assert oav.snapshot.filename.get() == "TIME_oav_snapshot_after_load"
    assert oav.snapshot.directory.get() == TEST_DIRECTORY

    webcam.trigger.assert_called_once()
    assert (await webcam.filename.get_value()) == "TIME_webcam_after_load"
    assert (await webcam.directory.get_value()) == TEST_DIRECTORY
