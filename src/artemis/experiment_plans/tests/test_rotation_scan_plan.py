from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.beamlines import i03
from ophyd.status import Status

from artemis.experiment_plans.rotation_scan_plan import (
    DIRECTION,
    OFFSET,
    get_plan,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan_plan,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)

if TYPE_CHECKING:
    from dodal.devices.backlight import Backlight
    from dodal.devices.detector_motion import DetectorMotion
    from dodal.devices.eiger import EigerDetector
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra


def test_move_to_start(smargon: Smargon, RE):
    start_angle = 153
    mock_velocity_set = MagicMock(return_value=Status(done=True, success=True))
    mock_omega_set = MagicMock(return_value=Status(done=True, success=True))
    with patch.object(smargon.omega.velocity, "set", mock_velocity_set):
        with patch.object(smargon.omega, "set", mock_omega_set):
            RE(move_to_start_w_buffer(smargon.omega, start_angle))

    mock_velocity_set.assert_called_with(120)
    mock_omega_set.assert_called_with(start_angle - OFFSET * DIRECTION)


def __fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


def test_move_to_end(smargon: Smargon, RE):
    scan_width = 153
    mock_omega_set = MagicMock(return_value=Status(done=True, success=True))

    with patch.object(smargon.omega, "set", mock_omega_set):
        with patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            __fake_read,
        ):
            RE(move_to_end_w_buffer(smargon.omega, scan_width))

    mock_omega_set.assert_called_with((scan_width + 0.1 + OFFSET) * DIRECTION)


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("artemis.experiment_plans.rotation_scan_plan.rotation_scan_plan")
def test_get_plan(
    plan: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    zebra.pc.armed.set(False)
    with (
        patch("dodal.beamlines.i03.smargon", return_value=smargon),
        patch("dodal.beamlines.i03.eiger", return_value=eiger),
        patch("dodal.beamlines.i03.zebra", return_value=zebra),
        patch("dodal.beamlines.i03.backlight", return_value=backlight),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.DetectorMotion",
            return_value=detector_motion,
        ),
    ):
        RE(get_plan(test_rotation_params, MagicMock()))

    eiger.stage.assert_called()
    eiger.unstage.assert_called()


@patch("bluesky.plan_stubs.wait")
def test_rotation_plan(
    bps_wait: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm_demand.set = mock_arm_disarm

    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    undulator = i03.undulator(fake_with_ophyd_sim=True)
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    slit_gaps = i03.s4_slit_gaps(fake_with_ophyd_sim=True)

    with (
        patch("dodal.beamlines.i03.undulator", return_value=undulator),
        patch("dodal.beamlines.i03.synchrotron", return_value=synchrotron),
        patch("dodal.beamlines.i03.s4_slit_gaps", return_value=slit_gaps),
    ):
        with patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            __fake_read,
        ):
            RE(
                rotation_scan_plan(
                    test_rotation_params,
                    eiger,
                    smargon,
                    zebra,
                    backlight,
                    detector_motion,
                )
            )

    # once for each velocity set and once for each position set for a total of 4 calls
    assert mock_omega_sets.call_count == 4


@patch("artemis.experiment_plans.rotation_scan_plan.cleanup_plan")
@patch("bluesky.plan_stubs.wait")
def test_cleanup_happens(
    bps_wait: MagicMock,
    cleanup_plan: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    smargon.omega.set = MagicMock(
        side_effect=Exception("Experiment fails because this is a test")
    )

    # check main subplan part fails
    with pytest.raises(Exception):
        RE(
            rotation_scan_plan(
                test_rotation_params, eiger, smargon, zebra, backlight, detector_motion
            )
        )
        cleanup_plan.assert_not_called()
    # check that failure is handled in composite plan
    with (
        patch("dodal.beamlines.i03.smargon", return_value=smargon),
        patch("dodal.beamlines.i03.eiger", return_value=eiger),
        patch("dodal.beamlines.i03.zebra", return_value=zebra),
        patch("dodal.beamlines.i03.backlight", return_value=backlight),
        patch("dodal.beamlines.i03.detector_motion", return_value=detector_motion),
    ):
        with pytest.raises(Exception):
            RE(
                get_plan(
                    test_rotation_params,
                    RotationCallbackCollection.from_params(test_rotation_params),
                )
            )
        cleanup_plan.assert_called_once()


@pytest.mark.s03()
@patch("bluesky.plan_stubs.wait")
def test_ispyb_deposition_in_plan(
    bps_wait: MagicMock,
    RE,
    test_rotation_params,
):
    def fake_create_devices():
        devices = {
            "eiger": i03.eiger(wait_for_connection=False, fake_with_ophyd_sim=True),
            "smargon": i03.smargon(),
            "zebra": i03.zebra(),
            "detector_motion": i03.detector_motion(fake_with_ophyd_sim=True),
            "backlight": i03.backlight(fake_with_ophyd_sim=True),
        }
        return devices

    undulator = i03.undulator(fake_with_ophyd_sim=True)
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    slit_gaps = i03.s4_slit_gaps(fake_with_ophyd_sim=True)

    with (
        patch(
            "artemis.experiment_plans.rotation_scan_plan.create_devices",
            fake_create_devices,
        ),
        patch("dodal.beamlines.i03.undulator", return_value=undulator),
        patch("dodal.beamlines.i03.synchrotron", return_value=synchrotron),
        patch("dodal.beamlines.i03.s4_slit_gaps", return_value=slit_gaps),
        patch("dodal.devices.eiger.EigerDetector.stage"),
    ):
        RE(
            get_plan(
                test_rotation_params,
                RotationCallbackCollection.from_params(test_rotation_params),
            )
        )
