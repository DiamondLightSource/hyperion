from typing import Generator
from unittest.mock import patch, MagicMock, ANY
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)

import pytest
import numpy as np

from typing import Dict
from dodal.beamlines.i03 import detector_motion
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.backlight import Backlight
from typing import List
from bluesky.callbacks import CallbackCounter
from dodal.devices.eiger import EigerDetector
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.aperturescatterguard import ApertureScatterguard
from bluesky import RunEngine

from artemis.experiment_plans.full_grid_scan import (
    create_devices,
    get_plan,
    wait_for_det_to_finish_moving,
    detect_grid_and_do_gridscan,
)

from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)


def _fake_grid_detection(
    parameters: OAVParameters,
    out_parameters,
    snapshot_template: str,
    snapshot_dir: str,
    out_snapshot_filenames: List[List[str]],
    out_upper_left: list[float] | np.ndarray,
    grid_width_px: int = 0,
    box_size_um: float = 0.0,
):
    out_snapshot_filenames.append([])
    out_snapshot_filenames.append([])
    out_parameters.x_start = 0
    out_parameters.y1_start = 0
    out_parameters.y2_start = 0
    out_parameters.z1_start = 0
    out_parameters.z2_start = 0
    out_parameters.x_steps = 0
    out_parameters.y_steps = 0
    out_parameters.z_steps = 0
    out_parameters.x_step_size = 0
    out_parameters.y_step_size = 0
    out_parameters.z_step_size = 0
    return []


def _fake_callbacks():
    return FGSCallbackCollection(
        ispyb_handler=CallbackCounter(),
        nexus_handler=CallbackCounter(),
        zocalo_handler=CallbackCounter(),
    )


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


def test_get_plan(test_params, mock_subscriptions, test_config_files):
    with patch("artemis.experiment_plans.full_grid_scan.i03"):
        plan = get_plan(test_params, mock_subscriptions, test_config_files)

    assert isinstance(plan, Generator)


@patch(
    "artemis.external_interaction.callbacks.fgs.fgs_callback_collection.FGSCallbackCollection.from_params",
    return_value=_fake_callbacks(),
)
@patch("artemis.experiment_plans.full_grid_scan.grid_detection_plan")
@patch("artemis.experiment_plans.full_grid_scan.fgs_get_plan")
def test_detect_grid_and_do_gridscan(
    mock_fast_grid_scan_plan: MagicMock,
    mock_grid_detection_plan: MagicMock,
    mock_fgs_callbacks: MagicMock,
    eiger: EigerDetector,
    backlight: Backlight,
    detector_motion: DetectorMotion,
    aperture_scatterguard: ApertureScatterguard,
    RE: RunEngine,
    test_full_grid_scan_params: GridScanWithEdgeDetectInternalParameters,
    mock_subscriptions: MagicMock,
    test_config_files: Dict,
):
    mock_grid_detection_plan.side_effect = _fake_grid_detection

    with patch.object(eiger.do_arm, "set", MagicMock()) as mock_eiger_set, patch.object(
        aperture_scatterguard, "set", MagicMock()
    ) as mock_aperture_scatterguard, patch.object(
        detector_motion.shutter, "get", MagicMock(return_value=1)
    ) as mock_shutter, patch.object(
        detector_motion.z.motor_done_move, "get", MagicMock(return_value=1)
    ) as mock_z_motor_move_done, patch.object(
        backlight.pos, "set", MagicMock()
    ) as mock_backlight_pos:
        RE(
            detect_grid_and_do_gridscan(
                parameters=test_full_grid_scan_params,
                backlight=backlight,
                eiger=eiger,
                aperture_scatterguard=aperture_scatterguard,
                detector_motion=detector_motion,
                oav_params=OAVParameters("xrayCentring", **test_config_files),
                experiment_params=test_full_grid_scan_params.experiment_params,
            )
        )

        # Check detector was armed
        mock_eiger_set.assert_called_once_with(1)

        # Verify we called the grid detection plan
        mock_grid_detection_plan.assert_called_once()

        # Check backlight was moved OUT
        mock_backlight_pos.assert_called_once_with(Backlight.OUT)

        # Check aperture was changed to SMALL
        mock_aperture_scatterguard.assert_called_once_with(
            aperture_scatterguard.aperture_positions.SMALL
        )

        # Check we read both shutter status and z_motor_move_done at
        # least once each (while waiting for detector motion)
        mock_shutter.assert_called()
        mock_z_motor_move_done.assert_called()

        # Check we called out to underlying fast grid scan plan
        mock_fast_grid_scan_plan.assert_called_once_with(ANY, mock_fgs_callbacks())
