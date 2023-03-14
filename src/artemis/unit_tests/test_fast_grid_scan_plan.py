import types
from unittest.mock import ANY, MagicMock, call, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.fast_grid_scan_composite import FGSComposite
from ophyd.sim import make_fake_device
from ophyd.status import Status

from artemis.exceptions import WarningException
from artemis.experiment_plans.fast_grid_scan_plan import (
    read_hardware_for_ispyb,
    run_gridscan,
    run_gridscan_and_move,
    wait_for_fgs_valid,
)
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from artemis.external_interaction.system_tests.conftest import (
    TEST_RESULT_LARGE,
    TEST_RESULT_MEDIUM,
    TEST_RESULT_SMALL,
)
from artemis.log import set_up_logging_handlers
from artemis.parameters.external_parameters import RawParameters
from artemis.parameters.internal_parameters import InternalParameters
from artemis.utils.utils import Point3D


@pytest.fixture
def test_params():
    return InternalParameters()


@pytest.fixture
def fake_fgs_composite():
    FakeComposite = make_fake_device(FGSComposite)
    fake_composite: FGSComposite = FakeComposite("test", name="fgs")
    fake_composite.aperture_scatterguard.aperture.x.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.y.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.z.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.scatterguard.x.user_setpoint._use_limits = (
        False
    )
    fake_composite.aperture_scatterguard.scatterguard.y.user_setpoint._use_limits = (
        False
    )
    fake_composite.aperture_scatterguard.load_aperture_positions(
        AperturePositions(
            LARGE=(1, 2, 3, 4, 5),
            MEDIUM=(2, 3, 3, 5, 6),
            SMALL=(3, 4, 3, 6, 7),
            ROBOT_LOAD=(0, 0, 3, 0, 0),
        )
    )

    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)
    fake_composite.fast_grid_scan.position_counter.sim_put(0)
    return fake_composite


@pytest.fixture
def mock_subscriptions(test_params):
    subscriptions = FGSCallbackCollection.from_params(test_params)
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_LARGE
    )

    subscriptions.nexus_handler.nxs_writer_1 = MagicMock()
    subscriptions.nexus_handler.nxs_writer_2 = MagicMock()

    subscriptions.ispyb_handler.ispyb = MagicMock()
    subscriptions.ispyb_handler.ispyb_ids = [[0, 0], 0, 0]

    return subscriptions


@pytest.fixture
def fake_eiger(test_params: InternalParameters):
    FakeEiger: EigerDetector = make_fake_device(EigerDetector)
    fake_eiger = FakeEiger.with_params(
        params=test_params.artemis_params.detector_params, name="test"
    )
    return fake_eiger


def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct():
    params = InternalParameters(RawParameters())
    assert (
        params.artemis_params.detector_params.detector_size_constants.det_type_string
        == EIGER_TYPE_EIGER2_X_16M
    )
    raw_params_dict = RawParameters().to_dict()
    raw_params_dict["artemis_params"]["detector_params"][
        "detector_size_constants"
    ] = EIGER_TYPE_EIGER2_X_4M
    raw_params = RawParameters.from_dict(raw_params_dict)
    params: InternalParameters = InternalParameters(raw_params)
    det_dimension = (
        params.artemis_params.detector_params.detector_size_constants.det_dimension
    )
    assert det_dimension == EIGER2_X_4M_DIMENSION


def test_when_run_gridscan_called_then_generator_returned():
    plan = run_gridscan(MagicMock(), MagicMock())
    assert isinstance(plan, types.GeneratorType)


def test_read_hardware_for_ispyb_updates_from_ophyd_devices(
    fake_fgs_composite: FGSComposite,
):
    RE = RunEngine({})
    params = InternalParameters()

    undulator_test_value = 1.234

    fake_fgs_composite.undulator.gap.user_readback.sim_put(undulator_test_value)

    synchrotron_test_value = "test"
    fake_fgs_composite.synchrotron.machine_status.synchrotron_mode.sim_put(
        synchrotron_test_value
    )

    xgap_test_value = 0.1234
    ygap_test_value = 0.2345
    fake_fgs_composite.s4_slit_gaps.xgap.user_readback.sim_put(xgap_test_value)
    fake_fgs_composite.s4_slit_gaps.ygap.user_readback.sim_put(ygap_test_value)

    test_ispyb_callback = FGSISPyBHandlerCallback(params)
    test_ispyb_callback.ispyb = MagicMock()
    RE.subscribe(test_ispyb_callback)

    def standalone_read_hardware_for_ispyb(und, syn, slits):
        yield from bps.open_run()
        yield from read_hardware_for_ispyb(und, syn, slits)
        yield from bps.close_run()

    RE(
        standalone_read_hardware_for_ispyb(
            fake_fgs_composite.undulator,
            fake_fgs_composite.synchrotron,
            fake_fgs_composite.s4_slit_gaps,
        )
    )
    params = test_ispyb_callback.params

    assert params.artemis_params.ispyb_params.undulator_gap == undulator_test_value
    assert params.artemis_params.ispyb_params.synchrotron_mode == synchrotron_test_value
    assert params.artemis_params.ispyb_params.slit_gap_size_x == xgap_test_value
    assert params.artemis_params.ispyb_params.slit_gap_size_y == ygap_test_value


@patch(
    "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range"
)
@patch("artemis.experiment_plans.fast_grid_scan_plan.run_gridscan")
@patch("artemis.experiment_plans.fast_grid_scan_plan.move_xyz")
def test_results_adjusted_and_passed_to_move_xyz(
    move_xyz: MagicMock,
    run_gridscan: MagicMock,
    move_aperture: MagicMock,
    fake_fgs_composite: FGSComposite,
    mock_subscriptions: FGSCallbackCollection,
    fake_eiger: EigerDetector,
    test_params: InternalParameters,
):
    RE = RunEngine({})
    set_up_logging_handlers(logging_level="INFO", dev_mode=True)
    RE.subscribe(VerbosePlanExecutionLoggingCallback())

    mock_subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_LARGE
    )
    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )
    mock_subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_MEDIUM
    )
    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )
    mock_subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_SMALL
    )
    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )

    call_large = call(
        *(fake_fgs_composite.aperture_scatterguard.aperture_positions.LARGE)
    )
    call_medium = call(
        *(fake_fgs_composite.aperture_scatterguard.aperture_positions.MEDIUM)
    )
    call_small = call(
        *(fake_fgs_composite.aperture_scatterguard.aperture_positions.SMALL)
    )

    move_aperture.assert_has_calls(
        [call_large, call_medium, call_small], any_order=True
    )


@patch("bluesky.plan_stubs.mv")
def test_results_passed_to_move_motors(
    bps_mv: MagicMock, test_params: InternalParameters
):
    from artemis.experiment_plans.fast_grid_scan_plan import move_xyz

    RE = RunEngine({})
    set_up_logging_handlers(logging_level="INFO", dev_mode=True)
    RE.subscribe(VerbosePlanExecutionLoggingCallback())
    motor_position = test_params.experiment_params.grid_position_to_motor_position(
        Point3D(1, 2, 3)
    )
    FakeComposite: FGSComposite = make_fake_device(FGSComposite)
    RE(move_xyz(FakeComposite("test", name="fgs").sample_motors, motor_position))
    bps_mv.assert_called_once_with(
        ANY, motor_position.x, ANY, motor_position.y, ANY, motor_position.z
    )


@patch(
    "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range"
)
@patch("artemis.experiment_plans.fast_grid_scan_plan.run_gridscan.do_fgs")
@patch("artemis.experiment_plans.fast_grid_scan_plan.run_gridscan")
@patch("artemis.experiment_plans.fast_grid_scan_plan.move_xyz")
def test_individual_plans_triggered_once_and_only_once_in_composite_run(
    move_xyz: MagicMock,
    run_gridscan: MagicMock,
    do_fgs: MagicMock,
    move_aperture: MagicMock,
    mock_subscriptions: FGSCallbackCollection,
    fake_fgs_composite: FGSComposite,
    fake_eiger: EigerDetector,
    test_params: FGSComposite,
):
    RE = RunEngine({})
    set_up_logging_handlers(logging_level="INFO", dev_mode=True)
    RE.subscribe(VerbosePlanExecutionLoggingCallback())
    params = InternalParameters()

    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )

    run_gridscan.assert_called_once_with(fake_fgs_composite, fake_eiger, params)
    move_xyz.assert_called_once_with(ANY, Point3D(0.05, 0.15000000000000002, 0.25))


@patch(
    "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range"
)
@patch("artemis.experiment_plans.fast_grid_scan_plan.run_gridscan.do_fgs")
@patch("artemis.experiment_plans.fast_grid_scan_plan.run_gridscan")
@patch("artemis.experiment_plans.fast_grid_scan_plan.move_xyz")
def test_logging_within_plan(
    move_xyz: MagicMock,
    run_gridscan: MagicMock,
    do_fgs: MagicMock,
    move_aperture: MagicMock,
    mock_subscriptions: FGSCallbackCollection,
    fake_fgs_composite: FGSComposite,
    fake_eiger: EigerDetector,
    test_params: InternalParameters,
):
    RE = RunEngine({})
    set_up_logging_handlers(logging_level="INFO", dev_mode=True)
    RE.subscribe(VerbosePlanExecutionLoggingCallback())

    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )

    run_gridscan.assert_called_once_with(fake_fgs_composite, fake_eiger, test_params)
    move_xyz.assert_called_once_with(ANY, Point3D(0.05, 0.15000000000000002, 0.25))


@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.sleep")
def test_GIVEN_scan_already_valid_THEN_wait_for_FGS_returns_immediately(
    patch_sleep: MagicMock,
):
    test_fgs: FastGridScan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")

    test_fgs.scan_invalid.sim_put(False)
    test_fgs.position_counter.sim_put(0)

    RE = RunEngine({})

    RE(wait_for_fgs_valid(test_fgs))

    patch_sleep.assert_not_called()


@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.sleep")
def test_GIVEN_scan_not_valid_THEN_wait_for_FGS_raises_and_sleeps_called(
    patch_sleep: MagicMock,
):
    test_fgs: FastGridScan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")

    test_fgs.scan_invalid.sim_put(True)
    test_fgs.position_counter.sim_put(0)

    RE = RunEngine({})
    with pytest.raises(WarningException):
        RE(wait_for_fgs_valid(test_fgs))

    patch_sleep.assert_called()


@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.abs_set")
@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.kickoff")
@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.complete")
@patch("artemis.experiment_plans.fast_grid_scan_plan.bps.mv")
def test_when_grid_scan_ran_then_eiger_disarmed_before_zocalo_end(
    mock_mv,
    mock_complete,
    mock_kickoff,
    mock_abs_set,
    fake_fgs_composite: FGSComposite,
    fake_eiger: EigerDetector,
    test_params: InternalParameters,
    mock_subscriptions: FGSCallbackCollection,
):
    RE = RunEngine({})

    # Put both mocks in a parent to easily capture order
    mock_parent = MagicMock()

    fake_eiger.disarm_detector = mock_parent.disarm

    fake_eiger.filewriters_finished = Status()
    fake_eiger.filewriters_finished.set_finished()
    fake_eiger.odin.check_odin_state = MagicMock(return_value=True)
    fake_eiger.stage = MagicMock()

    mock_subscriptions.zocalo_handler.zocalo_interactor.run_end = mock_parent.run_end

    RE(
        run_gridscan_and_move(
            fake_fgs_composite,
            fake_eiger,
            test_params,
            mock_subscriptions,
        )
    )

    mock_parent.assert_has_calls([call.disarm(), call.run_end(0), call.run_end(0)])
