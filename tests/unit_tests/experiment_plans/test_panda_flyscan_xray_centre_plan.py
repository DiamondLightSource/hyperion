import random
import types
from pathlib import Path
from typing import Any, Tuple
from unittest.mock import DEFAULT, MagicMock, call, patch

import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.detector.det_dim_constants import (
    EIGER2_X_4M_DIMENSION,
    EIGER_TYPE_EIGER2_X_4M,
    EIGER_TYPE_EIGER2_X_16M,
)
from dodal.devices.panda_fast_grid_scan import PandAFastGridScan
from dodal.devices.synchrotron import SynchrotronMode
from ophyd.sim import make_fake_device
from ophyd.status import Status
from ophyd_async.core import set_sim_value

from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
)
from hyperion.exceptions import WarningException
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
)
from hyperion.experiment_plans.panda_flyscan_xray_centre_plan import (
    SmargonSpeedException,
    panda_flyscan_xray_centre,
    read_hardware_for_ispyb_pre_collection,
    run_gridscan,
    run_gridscan_and_move,
    tidy_up_plans,
    wait_for_gridscan_valid,
)
from hyperion.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
    ispyb_activation_wrapper,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandAGridscanInternalParameters,
)

from ...conftest import default_raw_params
from ...system_tests.external_interaction.conftest import (
    TEST_RESULT_LARGE,
    TEST_RESULT_MEDIUM,
    TEST_RESULT_SMALL,
)
from ..external_interaction.callbacks.conftest import TestData
from .conftest import (
    assert_event,
    mock_zocalo_trigger,
    modified_interactor_mock,
    modified_store_grid_scan_mock,
    run_generic_ispyb_handler_setup,
)

PANDA_TEST_PARAMS_PATH = (
    "tests/test_data/parameter_json_files/panda_test_parameters.json"
)


@pytest.fixture
def RE_with_subs(RE: RunEngine, mock_subscriptions):
    for cb in list(mock_subscriptions):
        RE.subscribe(cb)
    yield RE, mock_subscriptions


@pytest.fixture
def ispyb_plan(test_panda_fgs_params):
    @bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_OUTER)
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            "hyperion_internal_parameters": test_panda_fgs_params.json(),
        }
    )
    def standalone_read_hardware_for_ispyb(
        und, syn, slits, robot, attn, fl, dcm, ap_sg
    ):
        yield from read_hardware_for_ispyb_pre_collection(und, syn, slits, ap_sg, robot)
        yield from read_hardware_for_ispyb_during_collection(attn, fl, dcm)

    return standalone_read_hardware_for_ispyb


@patch(
    "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.StoreInIspyb",
    modified_store_grid_scan_mock,
)
class TestFlyscanXrayCentrePlan:
    td: TestData = TestData()

    def test_given_full_parameters_dict_when_detector_name_used_and_converted_then_detector_constants_correct(
        self,
        test_panda_fgs_params: PandAGridscanInternalParameters,
    ):
        assert (
            test_panda_fgs_params.hyperion_params.detector_params.detector_size_constants.det_type_string
            == EIGER_TYPE_EIGER2_X_16M
        )
        raw_params_dict = default_raw_params()
        raw_params_dict["hyperion_params"]["detector_params"][
            "detector_size_constants"
        ] = EIGER_TYPE_EIGER2_X_4M
        params: PandAGridscanInternalParameters = PandAGridscanInternalParameters(
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

    def test_read_hardware_for_ispyb_updates_from_ophyd_devices(
        self,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
        RE: RunEngine,
        ispyb_plan,
    ):
        undulator_test_value = 1.234

        set_sim_value(fake_fgs_composite.undulator.current_gap, undulator_test_value)

        synchrotron_test_value = SynchrotronMode.USER
        set_sim_value(
            fake_fgs_composite.synchrotron.synchrotron_mode, synchrotron_test_value
        )

        transmission_test_value = 0.01
        fake_fgs_composite.attenuator.actual_transmission.sim_put(  # type: ignore
            transmission_test_value
        )

        xgap_test_value = 0.1234
        ygap_test_value = 0.2345
        fake_fgs_composite.s4_slit_gaps.xgap.user_readback.sim_put(xgap_test_value)  # type: ignore
        fake_fgs_composite.s4_slit_gaps.ygap.user_readback.sim_put(ygap_test_value)  # type: ignore
        flux_test_value = 10.0
        fake_fgs_composite.flux.flux_reading.sim_put(flux_test_value)  # type: ignore

        test_ispyb_callback = PlanReactiveCallback(ISPYB_LOGGER)
        test_ispyb_callback.active = True
        with patch.multiple(
            test_ispyb_callback,
            activity_gated_start=DEFAULT,
            activity_gated_event=DEFAULT,
        ):
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
            # fmt: off
            assert_event(
                test_ispyb_callback.activity_gated_start.mock_calls[0],  # pyright: ignore
                {
                    "plan_name": "standalone_read_hardware_for_ispyb",
                    "subplan_name": "run_gridscan_move_and_tidy",
                },
            )
            assert_event(
                test_ispyb_callback.activity_gated_event.mock_calls[0],  # pyright: ignore
                {
                    "undulator-current_gap": undulator_test_value,
                    "synchrotron-synchrotron_mode": synchrotron_test_value.value,
                    "s4_slit_gaps_xgap": xgap_test_value,
                    "s4_slit_gaps_ygap": ygap_test_value,
                },
            )
            assert_event(
                test_ispyb_callback.activity_gated_event.mock_calls[1],  # pyright: ignore
                {
                    "attenuator_actual_transmission": transmission_test_value,
                    "flux_flux_reading": flux_test_value,
                },
            )
            # fmt: on

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard._safe_move_within_datacollection_range",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    @pytest.mark.asyncio
    def test_results_adjusted_and_passed_to_move_xyz(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_x_y_z: MagicMock,
        run_gridscan: MagicMock,
        move_aperture: MagicMock,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        RE: RunEngine,
    ):
        RE.subscribe(VerbosePlanExecutionLoggingCallback())
        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_LARGE)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )
        )

        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_MEDIUM)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )
        )

        mock_zocalo_trigger(fake_fgs_composite.zocalo, TEST_RESULT_SMALL)
        RE(
            run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
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
            fake_fgs_composite.sample_motors,
            0.05,
            pytest.approx(0.15),
            0.25,
            wait=True,
        )
        mv_call_medium = call(
            fake_fgs_composite.sample_motors,
            0.05,
            pytest.approx(0.15),
            0.25,
            wait=True,
        )
        move_x_y_z.assert_has_calls(
            [mv_call_large, mv_call_large, mv_call_medium], any_order=True
        )

    @patch("bluesky.plan_stubs.abs_set", autospec=True)
    def test_results_passed_to_move_motors(
        self,
        bps_abs_set: MagicMock,
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        RE: RunEngine,
    ):
        from hyperion.device_setup_plans.manipulate_sample import move_x_y_z

        motor_position = (
            test_panda_fgs_params.experiment_params.grid_position_to_motor_position(
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
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_individual_plans_triggered_once_and_only_once_in_composite_run(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        move_aperture: MagicMock,
        RE_with_subs,
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
    ):
        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(
                mock_subscriptions[1], test_panda_fgs_params
            )
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE_with_subs[0](
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
            )
        )
        run_gridscan.assert_called_once()
        move_xyz.assert_called_once()

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard.set",
        return_value=Status(done=True, success=True),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_when_gridscan_finished_then_smargon_stub_offsets_are_set(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        aperture_set: MagicMock,
        RE_with_subs: tuple[RunEngine, Any],
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(
                mock_subscriptions[1], test_panda_fgs_params
            )
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE_with_subs[0](
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
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
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_when_gridscan_succeeds_ispyb_comment_appended_to(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        aperture_set: MagicMock,
        RE_with_subs: tuple[RunEngine, Any],
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        RE_with_subs[0].subscribe(VerbosePlanExecutionLoggingCallback())

        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(
                mock_subscriptions[1], test_panda_fgs_params
            )
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE_with_subs[0](
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
            )
        )
        app_to_comment: MagicMock = mock_subscriptions[
            1
        ].ispyb.append_to_comment  # type:ignore
        app_to_comment.assert_called()
        call = app_to_comment.call_args_list[0]
        assert "Crystal 1: Strength 999999" in call.args[1]

    @patch(
        "dodal.devices.aperturescatterguard.ApertureScatterguard.set",
        new=MagicMock(return_value=Status(done=True, success=True)),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        new=MagicMock(autospec=True),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        new=MagicMock(autospec=True),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        new=MagicMock(return_value=iter([])),
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.get_directory_provider",
        autospec=True,
    )
    def test_when_gridscan_run_panda_directory_applied(
        self,
        set_directory,
        RE_with_subs: tuple[RunEngine, Any],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        RE_with_subs[0].subscribe(VerbosePlanExecutionLoggingCallback())
        RE_with_subs[0](
            run_gridscan_and_move(fake_fgs_composite, test_panda_fgs_params)
        )
        expected_path = Path("/dls/i03/data/2023/cm33866-5/test_hyperion")
        set_directory.assert_called_once_with(expected_path)

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_when_gridscan_fails_ispyb_comment_appended_to(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        RE_with_subs: tuple[RunEngine, Any],
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
    ):
        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])

        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(
                mock_subscriptions[1], test_panda_fgs_params
            )
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE_with_subs[0](
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
            )
        )
        app_to_comment: MagicMock = mock_subscriptions[
            1
        ].ispyb.append_to_comment  # type:ignore
        app_to_comment.assert_called()
        call = app_to_comment.call_args_list[0]
        assert "Zocalo found no crystals in this gridscan" in call.args[1]

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.mv", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_GIVEN_no_results_from_zocalo_WHEN_communicator_wait_for_results_called_THEN_fallback_centre_used(
        self,
        mock_setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        mock_mv: MagicMock,
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
        test_panda_fgs_params: PandAGridscanInternalParameters,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        done_status,
    ):
        RE, (nexus_cb, ispyb_cb) = RE_with_subs
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
        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])

        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(ispyb_cb, test_panda_fgs_params)
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE(
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
            )
        )
        assert np.all(move_xyz.call_args[0][1:] == initial_x_y_z)

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_given_gridscan_fails_to_centre_then_stub_offsets_not_set(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        RE: RunEngine,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
    ):
        class MoveException(Exception):
            pass

        mock_zocalo_trigger(fake_fgs_composite.zocalo, [])
        move_xyz.side_effect = MoveException()

        with pytest.raises(MoveException):
            RE(run_gridscan_and_move(fake_fgs_composite, test_panda_fgs_params))
        assert (
            fake_fgs_composite.smargon.stub_offsets.center_at_current_position.proc.get()
            == 0
        )

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.run_gridscan",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.move_x_y_z",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_given_setting_stub_offsets_disabled_then_stub_offsets_not_set(
        self,
        setup_panda_for_flyscan: MagicMock,
        move_xyz: MagicMock,
        run_gridscan: MagicMock,
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
        RE: RunEngine,
        done_status,
    ):
        _, ispyb_cb = mock_subscriptions
        fake_fgs_composite.aperture_scatterguard.set = MagicMock(
            return_value=done_status
        )
        test_panda_fgs_params.experiment_params.set_stub_offsets = False

        RE.subscribe(VerbosePlanExecutionLoggingCallback())
        RE.subscribe(ispyb_cb)

        def wrapped_run_gridscan_and_move():
            run_generic_ispyb_handler_setup(ispyb_cb, test_panda_fgs_params)
            yield from run_gridscan_and_move(
                fake_fgs_composite,
                test_panda_fgs_params,
            )

        RE(
            ispyb_activation_wrapper(
                wrapped_run_gridscan_and_move(), test_panda_fgs_params
            )
        )
        assert (
            fake_fgs_composite.smargon.stub_offsets.center_at_current_position.proc.get()
            == 0
        )

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.sleep",
        autospec=True,
    )
    def test_GIVEN_scan_already_valid_THEN_wait_for_GRIDSCAN_returns_immediately(
        self, patch_sleep: MagicMock, RE: RunEngine
    ):
        test_fgs: PandAFastGridScan = make_fake_device(PandAFastGridScan)(
            "prefix", name="fake_fgs"
        )

        test_fgs.scan_invalid.sim_put(False)  # type: ignore
        test_fgs.position_counter.sim_put(0)  # type: ignore

        RE(wait_for_gridscan_valid(test_fgs))

        patch_sleep.assert_not_called()

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.sleep",
        autospec=True,
    )
    def test_GIVEN_scan_not_valid_THEN_wait_for_GRIDSCAN_raises_and_sleeps_called(
        self, patch_sleep: MagicMock, RE: RunEngine
    ):
        test_fgs: PandAFastGridScan = make_fake_device(PandAFastGridScan)(
            "prefix", name="fake_fgs"
        )

        test_fgs.scan_invalid.sim_put(True)  # type: ignore
        test_fgs.position_counter.sim_put(0)  # type: ignore
        with pytest.raises(WarningException):
            RE(wait_for_gridscan_valid(test_fgs))

        patch_sleep.assert_called()

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.abs_set",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.kickoff",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.complete",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.mv", autospec=True
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.wait_for_gridscan_valid",
        autospec=True,
    )
    @patch(
        "hyperion.external_interaction.nexus.write_nexus.NexusWriter",
        autospec=True,
        spec_set=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.setup_panda_for_flyscan",
        autospec=True,
    )
    def test_when_grid_scan_ran_then_eiger_disarmed_before_zocalo_end(
        self,
        nexuswriter,
        wait_for_valid,
        mock_setup_panda_for_flyscan,
        mock_mv,
        mock_complete,
        mock_kickoff,
        mock_abs_set,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
        mock_subscriptions: Tuple[GridscanNexusFileCallback, GridscanISPyBCallback],
        RE_with_subs: tuple[
            RunEngine, Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
        ],
    ):
        RE, (nexus_cb, ispyb_cb) = RE_with_subs
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

        with (
            patch(
                "hyperion.external_interaction.callbacks.xray_centre.nexus_callback.NexusWriter.create_nexus_file",
                autospec=True,
            ),
            patch(
                "hyperion.external_interaction.callbacks.zocalo_callback.ZocaloTrigger",
                lambda _: modified_interactor_mock(mock_parent.run_end),
            ),
        ):
            RE(
                ispyb_activation_wrapper(
                    panda_flyscan_xray_centre(
                        fake_fgs_composite, test_panda_fgs_params
                    ),
                    test_panda_fgs_params,
                )
            )

        mock_parent.assert_has_calls([call.disarm(), call.run_end(0), call.run_end(0)])

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.wait",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.complete",
        autospec=True,
    )
    def test_fgs_arms_eiger_without_grid_detect(
        self,
        mock_complete,
        mock_wait,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
        RE: RunEngine,
        done_status,
    ):
        fake_fgs_composite.eiger.unstage = MagicMock(return_value=done_status)

        RE(run_gridscan(fake_fgs_composite, test_panda_fgs_params))
        fake_fgs_composite.eiger.stage.assert_called_once()
        fake_fgs_composite.eiger.unstage.assert_called_once()

    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.wait",
        autospec=True,
    )
    @patch(
        "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.complete",
        autospec=True,
    )
    def test_when_grid_scan_fails_then_detector_disarmed_and_correct_exception_returned(
        self,
        mock_complete,
        mock_wait,
        fake_fgs_composite: FlyScanXRayCentreComposite,
        test_panda_fgs_params: PandAGridscanInternalParameters,
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
            RE(run_gridscan(fake_fgs_composite, test_panda_fgs_params))

        fake_fgs_composite.eiger.disable_roi_mode.assert_called()
        fake_fgs_composite.eiger.disarm_detector.assert_called()


def test_if_smargon_speed_over_limit_then_log_error(
    test_panda_fgs_params: PandAGridscanInternalParameters,
    fake_fgs_composite: FlyScanXRayCentreComposite,
    RE: RunEngine,
):
    test_panda_fgs_params.experiment_params.x_step_size = 10
    test_panda_fgs_params.hyperion_params.detector_params.exposure_time = 0.01

    with pytest.raises(SmargonSpeedException):
        RE(run_gridscan_and_move(fake_fgs_composite, test_panda_fgs_params))


# Ideally we'd have a test to check the tidy up plan is called upon any errors
@patch(
    "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.disarm_panda_for_gridscan",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.set_zebra_shutter_to_manual",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.panda_flyscan_xray_centre_plan.bps.wait",
    autospec=True,
)
def test_tidy_up_plans_disable_panda_and_zebra(
    mock_wait: MagicMock,
    mock_zebra_tidy: MagicMock,
    mock_panda_tidy: MagicMock,
    RE: RunEngine,
):
    RE(tidy_up_plans(MagicMock()))
    mock_panda_tidy.assert_called_once()
    mock_zebra_tidy.assert_called_once()
