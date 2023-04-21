from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from bluesky.utils import Msg
from ophyd.status import Status

from artemis.experiment_plans.rotation_scan_plan import (
    DIRECTION,
    OFFSET,
    get_plan,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan_plan,
)

if TYPE_CHECKING:
    from dodal.devices.eiger import EigerDetector
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra


def test_move_to_start(smargon: Smargon, RE):
    start_angle = 153
    mock_velocity_set = MagicMock(return_value=Status(done=True, success=True))
    mock_omega_set = MagicMock(return_value=Status(done=True, success=True))
    with patch.object(smargon.omega.velocity, "set", mock_velocity_set):
        with patch.object(smargon.omega, "set", mock_omega_set):
            RE(move_to_start_w_buffer(smargon, start_angle))

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
            # with patch.object(RE, "_read", MagicMock(return_value=0)):
            RE(move_to_end_w_buffer(smargon, scan_width))

    mock_omega_set.assert_called_with((scan_width + 0.1 + OFFSET) * DIRECTION)


@patch("artemis.experiment_plans.rotation_scan_plan.rotation_scan_plan")
def test_get_plan(
    plan: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    zebra.pc.armed.set(False)
    with patch("artemis.experiment_plans.rotation_scan_plan.smargon", smargon):
        with patch("artemis.experiment_plans.rotation_scan_plan.eiger", eiger):
            with patch("artemis.experiment_plans.rotation_scan_plan.zebra", zebra):
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
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm_demand.set = mock_arm_disarm

    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    with patch("artemis.experiment_plans.rotation_scan_plan.smargon", smargon):
        with patch("artemis.experiment_plans.rotation_scan_plan.eiger", eiger):
            with patch("artemis.experiment_plans.rotation_scan_plan.zebra", zebra):
                with patch(
                    "bluesky.preprocessors.__read_and_stash_a_motor",
                    __fake_read,
                ):
                    RE(rotation_scan_plan(test_rotation_params))

    assert mock_omega_sets.call_count == 4


# TODO test finally in get plan
