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
)

if TYPE_CHECKING:
    from dodal.devices.smargon import Smargon


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
def test_get_plan(plan: MagicMock, RE, test_rotation_params, smargon, zebra, eiger):
    plan.iter.return_value = iter([Msg("null"), Msg("null"), Msg("null")])
    eiger.stage = MagicMock()
    eiger.stage.iter.return_value = iter([Msg("null"), Msg("null"), Msg("null")])
    eiger.unstage = MagicMock()
    eiger.unstage.return_value = Msg("null")
    zebra.pc.armed.set(False)
    with patch("artemis.experiment_plans.rotation_scan_plan.smargon", smargon):
        with patch("artemis.experiment_plans.rotation_scan_plan.eiger", eiger):
            with patch("artemis.experiment_plans.rotation_scan_plan.zebra", zebra):
                RE(get_plan(test_rotation_params, MagicMock()))


# TODO test finally in get plan

# TODO test zebra rotation setup
