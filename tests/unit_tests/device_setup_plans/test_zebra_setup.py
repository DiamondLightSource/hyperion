from unittest.mock import MagicMock, call

import pytest
from bluesky import plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.zebra import (
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    I03Axes,
    Zebra,
)

from hyperion.device_setup_plans.setup_zebra import (
    bluesky_retry,
    set_zebra_shutter_to_manual,
    setup_zebra_for_gridscan,
    setup_zebra_for_rotation,
)


@pytest.fixture
def zebra():
    RunEngine()
    return i03.zebra(fake_with_ophyd_sim=True)


async def test_zebra_set_up_for_gridscan(RE, zebra: Zebra):
    RE(setup_zebra_for_gridscan(zebra, wait=True))
    assert await zebra.output.out_pvs[TTL_DETECTOR].get_value() == IN3_TTL
    assert await zebra.output.out_pvs[TTL_SHUTTER].get_value() == IN4_TTL


async def test_zebra_set_up_for_rotation(RE, zebra: Zebra):
    RE(setup_zebra_for_rotation(zebra, wait=True))
    assert await zebra.pc.gate_trigger.get_value() == I03Axes.OMEGA.value
    assert await zebra.pc.gate_width.get_value() == pytest.approx(360, 0.01)


async def test_zebra_cleanup(RE, zebra: Zebra):
    RE(set_zebra_shutter_to_manual(zebra, wait=True))
    assert await zebra.output.out_pvs[TTL_DETECTOR].get_value() == PC_PULSE
    assert await zebra.output.out_pvs[TTL_SHUTTER].get_value() == OR1


class MyException(Exception):
    pass


def test_when_first_try_fails_then_bluesky_retry_tries_again(RE, done_status):
    mock_device = MagicMock()

    @bluesky_retry
    def my_plan(value):
        yield from bps.abs_set(mock_device, value)

    mock_device.set.side_effect = [MyException(), done_status]

    RE(my_plan(10))

    assert mock_device.set.mock_calls == [call(10), call(10)]


def test_when_all_tries_fail_then_bluesky_retry_throws_error(RE, done_status):
    mock_device = MagicMock()

    @bluesky_retry
    def my_plan(value):
        yield from bps.abs_set(mock_device, value)

    exception_2 = MyException()
    mock_device.set.side_effect = [MyException(), exception_2]

    with pytest.raises(MyException) as e:
        RE(my_plan(10))

    assert e.value == exception_2
