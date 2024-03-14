import random
import types
from typing import Tuple
from unittest.mock import MagicMock, call, patch

import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import FailedStatus
from dodal.devices.detector.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.zocalo import ZocaloStartInfo
from ophyd.sim import make_fake_device
from ophyd.status import Status
from ophyd_async.core import set_sim_value

import hyperion.parameters.external_parameters
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.exceptions import WarningException
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
    kickoff_and_complete_gridscan,
    run_gridscan,
    run_gridscan_and_move,
    wait_for_gridscan_valid,
)
from hyperion.external_interaction.callbacks.common.callback_util import (
    create_gridscan_callbacks,
)
from hyperion.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.zocalo_callback import (
    ZocaloCallback,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from tests.conftest import create_dummy_scan_spec

from ...system_tests.external_interaction.conftest import (
    TEST_RESULT_LARGE,
    TEST_RESULT_MEDIUM,
    TEST_RESULT_SMALL,
)
from ..external_interaction.callbacks.conftest import TestData
from .conftest import (
    mock_zocalo_trigger,
    modified_interactor_mock,
    modified_store_grid_scan_mock,
    run_generic_ispyb_handler_setup,
)


@pytest.fixture
def ispyb_plan(test_fgs_params):
    @bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_OUTER)
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            "hyperion_internal_parameters": test_fgs_params.json(),
        }
    )
    def standalone_read_hardware_for_ispyb(
        und, syn, slits, robot, attn, fl, dcm, ap_sg
    ):
        yield from read_hardware_for_ispyb_pre_collection(und, syn, slits, ap_sg, robot)
        yield from read_hardware_for_ispyb_during_collection(attn, fl, dcm)

    return standalone_read_hardware_for_ispyb


@pytest.fixture
def RE_with_subs(RE: RunEngine, mock_subscriptions):
    for cb in list(mock_subscriptions):
        RE.subscribe(cb)
    yield RE, mock_subscriptions


@pytest.fixture
def mock_ispyb():
    return MagicMock()


@patch(
    "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb",
    modified_store_grid_scan_mock,
)
class TestFlyscanXrayCentrePlan:
    td: TestData = TestData()

    def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct(
        self,
        test_fgs_params: GridscanInternalParameters,
    ):
        assert (
            test_fgs_params.hyperion_params.detector_params.detector_size_constants.det_type_string
            == EIGER_TYPE_EIGER2_X_16M
        )
        raw_params_dict = hyperion.parameters.external_parameters.from_file()
        raw_params_dict["hyperion_params"]["detector_params"][
            "detector_size_constants"
        ] = EIGER_TYPE_EIGER2_X_4M
        params: GridscanInternalParameters = GridscanInternalParameters(
            **raw_params_dict
        )
        det_dimension = (
            params.hyperion_params.detector_params.detector_size_constants.det_dimension
        )
        assert det_dimension == EIGER2_X_4M_DIMENSION

    def test_when_run_gridscan_called_then_generator_returned(
        self,
    ):
        plan = run_gridscan(MagicMock(), MagicMock())
        assert isinstance(plan, types.GeneratorType)

    def test_when_run_gridscan_called_ispyb_deposition_made_and_records_errors(
        self,
        RE: RunEngine,
        fake_fgs_composite,
        test_fgs_params,
        mock_ispyb,
    ):
        ispyb_callback = GridscanISPyBCallback()
        RE.subscribe(ispyb_callback)

        error = None
        with pytest.raises(FailedStatus) as exc:
            with patch.object(
                fake_fgs_composite.sample_motors.omega, "set"
            ) as mock_set:
                error = AssertionError("Test Exception")
                mock_set.return_value = FailedStatus(error)

                RE(flyscan_xray_centre(fake_fgs_composite, test_fgs_params))

        assert exc.value.args[0] is error
        ispyb_callback.ispyb.end_deposition.assert_called_once_with(
            IspybIds(data_collection_group_id=0, data_collection_ids=(0, 0)),
            "fail",
            "Test Exception",
        )

    def test_read_hardware_for_ispyb_updates_from_ophyd_devices(
        self,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE: RunEngine,
        ispyb_plan,
    ):
        undulator_test_value = 1.234

        fake_fgs_composite.undulator.current_gap.sim_put(undulator_test_value)  # type: ignore

        synchrotron_test_value = "test"
        fake_fgs_composite.synchrotron.machine_status.synchrotron_mode.sim_put(  # type: ignore
            synchrotron_test_value
        )

        transmission_test_value = 0.01
        fake_fgs_composite.attenuator.actual_transmission.sim_put(  # type: ignore
            transmission_test_value
        )

        current_energy_kev_test_value = 12.05
        fake_fgs_composite.dcm.energy_in_kev.user_readback.sim_put(  # type: ignore
            current_energy_kev_test_value
        )

        xgap_test_value = 0.1234
        ygap_test_value = 0.2345
        fake_fgs_composite.s4_slit_gaps.xgap.user_readback.sim_put(xgap_test_value)  # type: ignore
        fake_fgs_composite.s4_slit_gaps.ygap.user_readback.sim_put(ygap_test_value)  # type: ignore
        flux_test_value = 10.0
        fake_fgs_composite.flux.flux_reading.sim_put(flux_test_value)  # type: ignore

        fake_fgs_composite.aperture_scatterguard.set(
            fake_fgs_composite.aperture_scatterguard.aperture_positions.LARGE  # type: ignore
        )
        set_sim_value(fake_fgs_composite.robot.barcode.bare_signal, ["BARCODE"])

        test_ispyb_callback = GridscanISPyBCallback()
        test_ispyb_callback.active = True
        test_ispyb_callback.ispyb = MagicMock(spec=StoreInIspyb)
        test_ispyb_callback.ispyb.begin_deposition.return_value = IspybIds(
            data_collection_ids=(2, 3), data_collection_group_id=5, grid_ids=(7, 8, 9)
        )
        RE.subscribe(test_ispyb_callback)

        RE(
            ispyb_plan(
                fake_fgs_composite.undulator,
                fake_fgs_composite.synchrotron,
                fake_fgs_composite.s4_slit_gaps,
                fake_fgs_composite.robot,
                fake_fgs_composite.attenuator,
                fake_fgs_composite.flux,
                fake_fgs_composite.dcm,
                fake_fgs_composite.aperture_scatterguard,
            )
        )
        hyperion_params = test_ispyb_callback.params.hyperion_params

        assert hyperion_params.ispyb_params.undulator_gap == undulator_test_value  # type: ignore
        assert (
            hyperion_params.ispyb_params.synchrotron_mode  # type: ignore
            == synchrotron_test_value
        )
        assert hyperion_params.ispyb_params.slit_gap_size_x == xgap_test_value  # type: ignore
        assert hyperion_params.ispyb_params.slit_gap_size_y == ygap_test_value  # type: ignore
        assert (
            hyperion_params.ispyb_params.transmission_fraction  # type: ignore
            == transmission_test_value
        )
        assert hyperion_params.ispyb_params.flux == flux_test_value  # type: ignore
        assert (
            hyperion_params.ispyb_params.current_energy_ev
            == current_energy_kev_test_value * 1000
        )

        assert hyperion_params.ispyb_params.sample_barcode == "BARCODE"

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    @pytest.mark.asyncio
    def test_results_adjusted_and_passed_to_move_xyz(
        self,
        move_x_y_z: MagicMock,
        run_gridscan: MagicMock,
        move_aperture: MagicMock,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
    ):
        RE, _ = RE_with_subs
        RE.subscribe(VerbosePlanExecutionLoggingCallback())

        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_LARGE)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )

        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_MEDIUM)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )

        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_SMALL)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )

        assert fake_fgs_composite.aperture_scatterguard.aperture_positions is not None
        ap_call_large = call(
            fake_fgs_composite.aperture_scatterguard.aperture_positions.LARGE.location
        )
        ap_call_medium = call(
            fake_fgs_composite.aperture_scatterguard.aperture_positions.MEDIUM.location
        )

        move_aperture.assert_has_calls(
            [ap_call_large, ap_call_large, ap_call_medium], any_order=True
        )

        mv_call_large = call(
            fake_fgs_composite.sample_motors, 0.05, pytest.approx(0.15), 0.25, wait=True
        )
        mv_call_medium = call(
            fake_fgs_composite.sample_motors, 0.05, pytest.approx(0.15), 0.25, wait=True
        )
        move_x_y_z.assert_has_calls(
            [mv_call_large, mv_call_large, mv_call_medium], any_order=True
        )

    @patch("bluesky.plan_stubs.abs_set", autospec=True)
    def test_results_passed_to_move_motors(
        self,
        bps_abs_set: MagicMock,
        test_fgs_params: GridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        RE: RunEngine,
    ):
        from hyperion.device_setup_plans.manipulate_sample import move_x_y_z

        motor_position = (
            test_fgs_params.experiment_params.grid_position_to_motor_position(
                np.array([1, 2, 3])
            )
        )
        RE(move_x_y_z(fake_fgs_composite.sample_motors, *motor_position))
        bps_abs_set.assert_has_calls(
            [
                call(
                    fake_fgs_composite.sample_motors.x,
                    motor_position[0],
                    group="move_x_y_z",
                ),
                call(
                    fake_fgs_composite.sample_motors.y,
                    motor_position[1],
                    group="move_x_y_z",
                ),
                call(
                    fake_fgs_composite.sample_motors.z,
                    motor_position[2],
                    group="move_x_y_z",
                ),
            ],
            any_order=True,
        )

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    @patch(
        "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
        modified_interactor_mock,
    )
    def test_individual_plans_triggered_once_and_only_once_in_composite_run(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        move_aperture: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
    ):
        RE, mock_subscriptions = RE_with_subs

        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        run_gridscan.assert_called_once()
        move_xyz.assert_called_once()

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard.set",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_when_gridscan_finished_then_smargon_stub_offsets_are_set(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        aperture_set: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        test_fgs_params: GridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        RE, mock_subscriptions = RE_with_subs
        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)

        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        assert (
            fake_fgs_composite.smargon.stub_offsets.center_at_current_position.proc.get()
            == 1
        )

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard.set",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_when_gridscan_succeeds_ispyb_comment_appended_to(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        aperture_set: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        test_fgs_params: GridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        RE, mock_subscriptions = RE_with_subs
        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)

        RE.subscribe(VerbosePlanExecutionLoggingCallback())

        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        app_to_comment: MagicMock = mock_subscriptions[
            1
        ].ispyb.append_to_comment  # type:ignore
        app_to_comment.assert_called()
        call = app_to_comment.call_args_list[0]
        assert "Crystal 1: Strength 999999" in call.args[1]

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_when_gridscan_fails_ispyb_comment_appended_to(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        test_fgs_params: GridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        RE, mock_subscriptions = RE_with_subs
        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)
        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        app_to_comment: MagicMock = mock_subscriptions[
            1
        ].ispyb.append_to_comment  # type:ignore
        app_to_comment.assert_called()
        call = app_to_comment.call_args_list[0]
        assert "Zocalo found no crystals in this gridscan" in call.args[1]

    @patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.mv", autospec=True)
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_GIVEN_no_results_from_zocalo_WHEN_communicator_wait_for_results_called_THEN_fallback_centre_used(
        self,
        move_xyz: MagicMock,
        mock_mv: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        test_fgs_params: GridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        done_status,
    ):
        RE, mock_subscriptions = RE_with_subs
        fake_fgs_composite.eiger.unstage = MagicMock(return_value=done_status)
        initial_x_y_z = np.array(
            [
                random.uniform(-0.5, 0.5),
                random.uniform(-0.5, 0.5),
                random.uniform(-0.5, 0.5),
            ]
        )
        fake_fgs_composite.smargon.x.user_readback.sim_put(initial_x_y_z[0])  # type: ignore
        fake_fgs_composite.smargon.y.user_readback.sim_put(initial_x_y_z[1])  # type: ignore
        fake_fgs_composite.smargon.z.user_readback.sim_put(initial_x_y_z[2])  # type: ignore
        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)
        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        assert np.all(move_xyz.call_args[0][1:] == initial_x_y_z)

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_given_gridscan_fails_to_centre_then_stub_offsets_not_set(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        RE: RunEngine,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
    ):
        class MoveException(Exception):
            pass

        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])
        move_xyz.side_effect = MoveException()

        with pytest.raises(MoveException):
            RE(run_gridscan_and_move(fake_fgs_composite, test_fgs_params))
        assert (
            fake_fgs_composite.smargon.stub_offsets.center_at_current_position.proc.get()
            == 0
        )

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.run_gridscan", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.move_x_y_z", autospec=True
    )
    def test_given_setting_stub_offsets_disabled_then_stub_offsets_not_set(
        self,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        done_status,
    ):
        RE, mock_subscriptions = RE_with_subs
        fake_fgs_composite.aperture_scatterguard.set = MagicMock(
            return_value=done_status
        )
        test_fgs_params.experiment_params.set_stub_offsets = False
        run_generic_ispyb_handler_setup(mock_subscriptions[1], test_fgs_params)

        RE.subscribe(VerbosePlanExecutionLoggingCallback())

        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_fgs_params,
            )
        )
        assert (
            fake_fgs_composite.smargon.stub_offsets.center_at_current_position.proc.get()
            == 0
        )

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.sleep", autospec=True
    )
    def test_GIVEN_scan_already_valid_THEN_wait_for_GRIDSCAN_returns_immediately(
        self, patch_sleep: MagicMock, RE: RunEngine
    ):
        test_fgs: FastGridScan = make_fake_device(FastGridScan)(
            "prefix", name="fake_fgs"
        )

        test_fgs.scan_invalid.sim_put(False)  # type: ignore
        test_fgs.position_counter.sim_put(0)  # type: ignore

        RE(wait_for_gridscan_valid(test_fgs))

        patch_sleep.assert_not_called()

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.sleep", autospec=True
    )
    def test_GIVEN_scan_not_valid_THEN_wait_for_GRIDSCAN_raises_and_sleeps_called(
        self, patch_sleep: MagicMock, RE: RunEngine
    ):
        test_fgs: FastGridScan = make_fake_device(FastGridScan)(
            "prefix", name="fake_fgs"
        )

        test_fgs.scan_invalid.sim_put(True)  # type: ignore
        test_fgs.position_counter.sim_put(0)  # type: ignore
        with pytest.raises(WarningException):
            RE(wait_for_gridscan_valid(test_fgs))

        patch_sleep.assert_called()

    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.abs_set", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.kickoff", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.complete", autospec=True
    )
    @patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.mv", autospec=True)
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.wait_for_gridscan_valid",
        autospec=True,
    )
    @patch(
        "hyperion.external_interaction.nexus.write_nexus.NexusWriter",
        autospec=True,
        spec_set=True,
    )
    def test_when_grid_scan_ran_then_eiger_disarmed_before_zocalo_end(
        self,
        nexuswriter,
        wait_for_valid,
        mock_mv,
        mock_complete,
        mock_kickoff,
        mock_abs_set,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
    ):
        RE, mock_subscriptions = RE_with_subs
        # Put both mocks in a parent to easily capture order
        mock_parent = MagicMock()
        fake_fgs_composite.eiger.disarm_detector = mock_parent.disarm

        fake_fgs_composite.eiger.filewriters_finished = Status(done=True, success=True)  # type: ignore
        fake_fgs_composite.eiger.odin.check_odin_state = MagicMock(return_value=True)
        fake_fgs_composite.eiger.odin.file_writer.num_captured.sim_put(1200)  # type: ignore
        fake_fgs_composite.eiger.stage = MagicMock(
            return_value=Status(None, None, 0, True, True)
        )
        fake_fgs_composite.xbpm_feedback.pos_stable.sim_put(1)  # type: ignore

        with patch(
            "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter.create_nexus_file",
            autospec=True,
        ), patch(
            "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
            lambda _: modified_interactor_mock(mock_parent.run_end),
        ):
            [RE.subscribe(cb) for cb in list(mock_subscriptions)]
            RE(flyscan_xray_centre(fake_fgs_composite, test_fgs_params))

        mock_parent.assert_has_calls([call.disarm(), call.run_end(0), call.run_end(0)])

    @patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.wait", autospec=True)
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.complete", autospec=True
    )
    def test_fgs_arms_eiger_without_grid_detect(
        self,
        mock_complete,
        mock_wait,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE: RunEngine,
    ):
        fake_fgs_composite.eiger.stage = MagicMock()
        fake_fgs_composite.eiger.unstage = MagicMock()

        RE(run_gridscan(fake_fgs_composite, test_fgs_params))
        fake_fgs_composite.eiger.stage.assert_called_once()
        fake_fgs_composite.eiger.unstage.assert_called_once()

    @patch("hyperion.experiment_plans.flyscan_xray_centre_plan.bps.wait", autospec=True)
    @patch(
        "hyperion.experiment_plans.flyscan_xray_centre_plan.bps.complete", autospec=True
    )
    def test_when_grid_scan_fails_then_detector_disarmed_and_correct_exception_returned(
        self,
        mock_complete,
        mock_wait,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_fgs_params: GridscanInternalParameters,
        RE: RunEngine,
    ):
        class CompleteException(Exception):
            pass

        mock_complete.side_effect = CompleteException()

        fake_fgs_composite.eiger.stage = MagicMock(
            return_value=Status(None, None, 0, True, True)
        )

        fake_fgs_composite.eiger.odin.check_odin_state = MagicMock()

        fake_fgs_composite.eiger.disarm_detector = MagicMock()
        fake_fgs_composite.eiger.disable_roi_mode = MagicMock()

        # Without the complete finishing we will not get all the images
        fake_fgs_composite.eiger.ALL_FRAMES_TIMEOUT = 0.1  # type: ignore

        # Want to get the underlying completion error, not the one raised from unstage
        with pytest.raises(CompleteException):
            RE(run_gridscan(fake_fgs_composite, test_fgs_params))

        fake_fgs_composite.eiger.disable_roi_mode.assert_called()
        fake_fgs_composite.eiger.disarm_detector.assert_called()


@patch(
    "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
    autospec=True,
)
def test_kickoff_and_complete_gridscan_triggers_zocalo(
    mock_zocalo_trigger_class: MagicMock,
    RE: RunEngine,
    fake_fgs_composite: FlyScanXRayCentreComposite,
):
    id_1, id_2 = 100, 200

    _,  ispyb_cb= create_gridscan_callbacks()
    ispyb_cb.active = True
    ispyb_cb.ispyb = MagicMock()
    ispyb_cb.params = MagicMock()
    ispyb_cb.ispyb_ids.data_collection_ids = (id_1, id_2)
    assert isinstance(zocalo_cb := ispyb_cb.emit_cb, ZocaloCallback)
    zocalo_env = "dev_env"

    zocalo_cb.start({CONST.TRIGGER.ZOCALO: CONST.PLAN.DO_FGS})  # type: ignore
    assert zocalo_cb.triggering_plan == CONST.PLAN.DO_FGS

    mock_zocalo_trigger_class.return_value = (mock_zocalo_trigger := MagicMock())

    fake_fgs_composite.eiger.unstage = MagicMock()
    fake_fgs_composite.eiger.odin.file_writer.id.sim_put("test/filename")  # type: ignore

    x_steps, y_steps, z_steps = 10, 20, 30

    RE.subscribe(ispyb_cb)
    RE(
        kickoff_and_complete_gridscan(
            fake_fgs_composite.fast_grid_scan,
            fake_fgs_composite.eiger,
            fake_fgs_composite.synchrotron,
            zocalo_env,
            scan_points=create_dummy_scan_spec(x_steps, y_steps, z_steps),
        )
    )

    mock_zocalo_trigger_class.assert_called_once_with(zocalo_env)

    expected_start_infos = [
        ZocaloStartInfo(id_1, "test/filename", 0, x_steps * y_steps),
        ZocaloStartInfo(id_2, "test/filename", x_steps * y_steps, x_steps * z_steps),
    ]

    expected_start_calls = [
        call(expected_start_infos[0]),
        call(expected_start_infos[1]),
    ]

    assert mock_zocalo_trigger.run_start.call_count == 2
    assert mock_zocalo_trigger.run_start.mock_calls == expected_start_calls

    assert mock_zocalo_trigger.run_end.call_count == 2
    assert mock_zocalo_trigger.run_end.mock_calls == [call(id_1), call(id_2)]
