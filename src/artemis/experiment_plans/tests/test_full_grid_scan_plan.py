from typing import Generator
from unittest.mock import patch

import pytest
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.i03 import detector_motion

from artemis.experiment_plans.full_grid_scan import (
    create_devices,
    get_plan,
    wait_for_det_to_finish_moving,
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
