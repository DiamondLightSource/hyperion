from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon

from artemis.exceptions import WarningException
from artemis.experiment_plans.pin_tip_centring_plan import move_pin_into_view


def test_given_the_pin_tip_is_already_in_view_when_get_tip_into_view_then_tip_returned_and_smargon_not_moved(
    smargon: Smargon, oav: OAV
):
    smargon.x.user_readback.sim_put(0)
    oav.mxsc.pin_tip.tip_x.sim_put(100)
    oav.mxsc.pin_tip.tip_y.sim_put(200)

    oav.mxsc.pin_tip.trigger = MagicMock(side_effect=oav.mxsc.pin_tip.trigger)

    RE = RunEngine(call_returns_result=True)
    result = RE(move_pin_into_view(oav, smargon))

    oav.mxsc.pin_tip.trigger.assert_called_once()
    assert smargon.x.user_readback.get() == 0
    assert result.plan_result == (100, 200)


def test_given_no_tip_found_but_will_be_found_when_get_tip_into_view_then_smargon_moved_positive_and_tip_returned(
    smargon: Smargon, oav: OAV
):
    oav.mxsc.pin_tip.triggered_tip.put(oav.mxsc.pin_tip.INVALID_POSITION)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    smargon.x.user_readback.sim_put(0)

    def set_pin_tip_when_x_moved(*args, **kwargs):
        oav.mxsc.pin_tip.tip_x.sim_put(100)
        oav.mxsc.pin_tip.tip_y.sim_put(200)

    smargon.x.subscribe(set_pin_tip_when_x_moved, run=False)

    RE = RunEngine(call_returns_result=True)
    result = RE(move_pin_into_view(oav, smargon))

    assert smargon.x.user_readback.get() == 1
    assert result.plan_result == (100, 200)


def test_given_tip_at_zero_but_will_be_found_when_get_tip_into_view_then_smargon_moved_negative_and_tip_returned(
    smargon: Smargon, oav: OAV
):
    oav.mxsc.pin_tip.tip_x.sim_put(0)
    oav.mxsc.pin_tip.tip_y.sim_put(100)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    smargon.x.user_readback.sim_put(0)

    def set_pin_tip_when_x_moved(*args, **kwargs):
        oav.mxsc.pin_tip.tip_x.sim_put(100)
        oav.mxsc.pin_tip.tip_y.sim_put(200)

    smargon.x.subscribe(set_pin_tip_when_x_moved, run=False)

    RE = RunEngine(call_returns_result=True)
    result = RE(move_pin_into_view(oav, smargon))

    assert smargon.x.user_readback.get() == -1
    assert result.plan_result == (100, 200)


def test_given_no_tip_found_ever_when_get_tip_into_view_then_smargon_moved_positive_and_exception_thrown(
    smargon: Smargon, oav: OAV
):
    oav.mxsc.pin_tip.triggered_tip.put(oav.mxsc.pin_tip.INVALID_POSITION)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    smargon.x.user_readback.sim_put(0)

    with pytest.raises(WarningException):
        RE = RunEngine(call_returns_result=True)
        RE(move_pin_into_view(oav, smargon))

    assert smargon.x.user_readback.get() == 1
