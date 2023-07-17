from typing import Dict, Generator
from unittest.mock import ANY, MagicMock, patch

import pytest
from bluesky import RunEngine
from dodal.beamlines.i03 import detector_motion
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAVParameters
from numpy.testing import assert_array_equal

from artemis.experiment_plans.full_grid_scan import (
    create_devices,
    detect_grid_and_do_gridscan,
    get_plan,
    start_arming_then_do_grid,
    wait_for_det_to_finish_moving,
)
from artemis.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)


def _fake_grid_detection(
    parameters: OAVParameters,
    out_parameters,
    snapshot_template: str,
    snapshot_dir: str,
    grid_width_px: int = 0,
    box_size_um: float = 0.0,
):
    out_parameters.x_start = 0
    out_parameters.y1_start = 0
    out_parameters.y2_start = 0
    out_parameters.z1_start = 0
    out_parameters.z2_start = 0
    out_parameters.x_steps = 10
    out_parameters.y_steps = 2
    out_parameters.z_steps = 2
    out_parameters.x_step_size = 1
    out_parameters.y_step_size = 1
    out_parameters.z_step_size = 1
    return []


@patch("artemis.experiment_plans.full_grid_scan.get_beamline_parameters")
def test_create_devices(mock_beamline_params):
    with (
        patch("artemis.experiment_plans.full_grid_scan.i03") as i03,
        patch(
            "artemis.experiment_plans.full_grid_scan.fgs_create_devices"
        ) as fgs_create_devices,
        patch(
            "artemis.experiment_plans.full_grid_scan.oav_create_devices"
        ) as oav_create_devices,
    ):
        create_devices()
        fgs_create_devices.assert_called()
        oav_create_devices.assert_called()

        i03.detector_motion.assert_called()
        i03.backlight.assert_called()
        assert isinstance(
            i03.aperture_scatterguard.call_args.args[-1], AperturePositions
        )


def test_wait_for_detector(RE):
    d_m = detector_motion(fake_with_ophyd_sim=True)
    with pytest.raises(TimeoutError):
        RE(wait_for_det_to_finish_moving(d_m, 0.2))
    d_m.shutter.sim_put(1)
    d_m.z.motor_done_move.sim_put(1)
    RE(wait_for_det_to_finish_moving(d_m, 0.5))


def test_get_plan(test_fgs_params, test_config_files):
    with patch("artemis.experiment_plans.full_grid_scan.i03"):
        plan = get_plan(test_fgs_params, test_config_files)

    assert isinstance(plan, Generator)


@patch(
    "artemis.experiment_plans.full_grid_scan.wait_for_det_to_finish_moving",
    autospec=True,
)
@patch("artemis.experiment_plans.full_grid_scan.grid_detection_plan", autospec=True)
@patch("artemis.experiment_plans.full_grid_scan.fgs_get_plan", autospec=True)
@patch(
    "artemis.experiment_plans.full_grid_scan.OavSnapshotCallback",
    autospec=True,
)
def test_detect_grid_and_do_gridscan(
    mock_oav_callback_init: MagicMock,
    mock_fast_grid_scan_plan: MagicMock,
    mock_grid_detection_plan: MagicMock,
    mock_wait_for_detector: MagicMock,
    backlight: Backlight,
    detector_motion: DetectorMotion,
    aperture_scatterguard: ApertureScatterguard,
    RE: RunEngine,
    test_full_grid_scan_params: GridScanWithEdgeDetectInternalParameters,
    test_config_files: Dict,
):
    mock_oav_callback = OavSnapshotCallback()
    mock_oav_callback.out_upper_left = [[0, 1], [2, 3]]
    mock_oav_callback.snapshot_filenames = [["test"], ["test3"]]
    mock_oav_callback_init.return_value = mock_oav_callback
    mock_grid_detection_plan.side_effect = _fake_grid_detection

    with patch.object(
        aperture_scatterguard, "set", MagicMock()
    ) as mock_aperture_scatterguard:
        RE(
            detect_grid_and_do_gridscan(
                parameters=test_full_grid_scan_params,
                backlight=backlight,
                aperture_scatterguard=aperture_scatterguard,
                detector_motion=detector_motion,
                oav_params=OAVParameters("xrayCentring", **test_config_files),
            )
        )
        # Verify we called the grid detection plan
        mock_grid_detection_plan.assert_called_once()

        # Verify callback to oav snaposhot was called
        mock_oav_callback_init.assert_called_once()

        # Check backlight was moved OUT
        assert backlight.pos.get() == Backlight.OUT

        # Check aperture was changed to SMALL
        mock_aperture_scatterguard.assert_called_once_with(
            aperture_scatterguard.aperture_positions.SMALL
        )

        # Check we wait for detector to finish moving
        mock_wait_for_detector.assert_called_once()

        # Check we called out to underlying fast grid scan plan
        mock_fast_grid_scan_plan.assert_called_once_with(ANY)


@patch(
    "artemis.experiment_plans.full_grid_scan.wait_for_det_to_finish_moving",
    autospec=True,
)
@patch("artemis.experiment_plans.full_grid_scan.grid_detection_plan", autospec=True)
@patch("artemis.experiment_plans.full_grid_scan.fgs_get_plan", autospec=True)
@patch("artemis.experiment_plans.full_grid_scan.OavSnapshotCallback", autospec=True)
def test_when_full_grid_scan_run_then_parameters_sent_to_fgs_as_expected(
    mock_oav_callback_init: MagicMock,
    mock_fast_grid_scan_plan: MagicMock,
    mock_grid_detection_plan: MagicMock,
    _: MagicMock,
    eiger: EigerDetector,
    backlight: Backlight,
    detector_motion: DetectorMotion,
    aperture_scatterguard: ApertureScatterguard,
    RE: RunEngine,
    test_full_grid_scan_params: GridScanWithEdgeDetectInternalParameters,
    test_config_files: Dict,
):
    mock_oav_callback = OavSnapshotCallback()
    mock_oav_callback.snapshot_filenames = [["a", "b", "c"], ["d", "e", "f"]]
    mock_oav_callback.out_upper_left = [[1, 2], [1, 3]]

    mock_oav_callback_init.return_value = mock_oav_callback

    mock_grid_detection_plan.side_effect = _fake_grid_detection

    with patch.object(eiger.do_arm, "set", MagicMock()), patch.object(
        aperture_scatterguard, "set", MagicMock()
    ):
        RE(
            detect_grid_and_do_gridscan(
                parameters=test_full_grid_scan_params,
                backlight=backlight,
                aperture_scatterguard=aperture_scatterguard,
                detector_motion=detector_motion,
                oav_params=OAVParameters("xrayCentring", **test_config_files),
            )
        )

        params: FGSInternalParameters = mock_fast_grid_scan_plan.call_args[0][0]

        assert isinstance(params, FGSInternalParameters)

        ispyb_params = params.artemis_params.ispyb_params
        assert_array_equal(ispyb_params.upper_left, [1, 2, 3])
        assert ispyb_params.xtal_snapshots_omega_start == [
            "c",
            "b",
            "a",
        ]
        assert ispyb_params.xtal_snapshots_omega_end == [
            "f",
            "e",
            "d",
        ]

        assert params.artemis_params.detector_params.num_triggers == 40

        assert params.experiment_params.x_axis.full_steps == 10
        assert params.experiment_params.y_axis.end == 1

        # Parameters can be serialized
        params.json()


@patch("artemis.experiment_plans.full_grid_scan.grid_detection_plan")
@patch("artemis.experiment_plans.full_grid_scan.OavSnapshotCallback")
def test_grid_detection_running_when_exception_raised_then_eiger_unstaged(
    mock_oav_callback: MagicMock,
    mock_grid_detection_plan: MagicMock,
    RE: RunEngine,
    test_full_grid_scan_params: GridScanWithEdgeDetectInternalParameters,
    mock_subscriptions: MagicMock,
    test_config_files: Dict,
):
    mock_grid_detection_plan.side_effect = Exception()
    eiger: EigerDetector = MagicMock(spec=EigerDetector)

    with patch(
        "artemis.external_interaction.callbacks.fgs.fgs_callback_collection.FGSCallbackCollection.from_params",
        return_value=mock_subscriptions,
    ):
        with pytest.raises(Exception):
            RE(
                start_arming_then_do_grid(
                    parameters=test_full_grid_scan_params,
                    backlight=MagicMock(),
                    eiger=eiger,
                    aperture_scatterguard=MagicMock(),
                    detector_motion=MagicMock(),
                    oav_params=OAVParameters("xrayCentring", **test_config_files),
                )
            )

        # Check detector was armed
        eiger.do_arm.set.assert_called_once_with(1)

        eiger.unstage.assert_called_once()
