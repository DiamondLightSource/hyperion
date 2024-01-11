from unittest.mock import patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode

from hyperion.device_setup_plans.check_topup import (
    check_topup_and_wait_if_necessary,
    wait_for_topup_complete,
)


@pytest.fixture
def synchrotron() -> Synchrotron:
    return i03.synchrotron(fake_with_ophyd_sim=True)


@patch("hyperion.device_setup_plans.check_topup.wait_for_topup_complete")
@patch("hyperion.device_setup_plans.check_topup.bps.sleep")
def test_when_topup_before_end_of_collection_wait(
    fake_sleep, fake_wait, synchrotron: Synchrotron
):
    synchrotron.machine_status.synchrotron_mode.sim_put(SynchrotronMode.USER.value)  # type: ignore
    synchrotron.top_up.start_countdown.sim_put(20.0)  # type: ignore
    synchrotron.top_up.end_countdown.sim_put(60.0)  # type: ignore

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            total_exposure_time=40.0,
            ops_time=30.0,
        )
    )
    fake_sleep.assert_called_once_with(60.0)


@patch("hyperion.device_setup_plans.check_topup.bps.rd")
@patch("hyperion.device_setup_plans.check_topup.bps.sleep")
def test_wait_for_topup_complete(fake_sleep, fake_rd, synchrotron):
    def fake_generator(value):
        yield from bps.null()
        return value

    fake_rd.side_effect = [
        fake_generator(0.0),
        fake_generator(0.0),
        fake_generator(0.0),
        fake_generator(10.0),
    ]

    RE = RunEngine()
    RE(wait_for_topup_complete(synchrotron))

    assert fake_sleep.call_count == 3
    fake_sleep.assert_called_with(0.1)


@patch("hyperion.device_setup_plans.check_topup.bps.sleep")
@patch("hyperion.device_setup_plans.check_topup.bps.null")
def test_no_waiting_if_decay_mode(fake_null, fake_sleep, synchrotron: Synchrotron):
    synchrotron.top_up.start_countdown.sim_put(-1)  # type: ignore

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            total_exposure_time=10.0,
            ops_time=1.0,
        )
    )
    fake_null.assert_called_once()
    assert fake_sleep.call_count == 0


@patch("hyperion.device_setup_plans.check_topup.bps.null")
def test_no_waiting_when_mode_does_not_allow_gating(
    fake_null, synchrotron: Synchrotron
):
    synchrotron.top_up.start_countdown.sim_put(1.0)  # type: ignore
    synchrotron.machine_status.synchrotron_mode.sim_put(SynchrotronMode.SHUTDOWN.value)  # type: ignore

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            total_exposure_time=10.0,
            ops_time=1.0,
        )
    )
    fake_null.assert_called_once()
