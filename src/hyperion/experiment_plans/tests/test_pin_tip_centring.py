from functools import partial
from unittest.mock import MagicMock, patch

import pytest
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon
from ophyd_async.core import set_sim_value

from hyperion.exceptions import WarningException
from hyperion.experiment_plans.pin_tip_centring_plan import (
    DEFAULT_STEP_SIZE,
    PinTipCentringComposite,
    move_pin_into_view,
    move_smargon_warn_on_out_of_range,
    pin_tip_centre_plan,
)


@pytest.mark.asyncio
async def test_given_the_pin_tip_is_already_in_view_when_get_tip_into_view_then_tip_returned_and_smargon_not_moved(
    oav: OAV, RE: RunEngine, smargon: Smargon
):
    set_sim_value(smargon.x.readback, 0)
    oav.mxsc.pin_tip.tip_x.sim_put(100)
    oav.mxsc.pin_tip.tip_y.sim_put(200)

    oav.mxsc.pin_tip.trigger = MagicMock(side_effect=oav.mxsc.pin_tip.trigger)

    result = RE(move_pin_into_view(oav, smargon))

    oav.mxsc.pin_tip.trigger.assert_called_once()
    assert await smargon.x.readback.get_value() == 0
    assert result.plan_result == (100, 200)


@pytest.mark.asyncio
async def test_given_no_tip_found_but_will_be_found_when_get_tip_into_view_then_smargon_moved_positive_and_tip_returned(
    oav: OAV, RE: RunEngine, smargon: Smargon
):
    oav.mxsc.pin_tip.triggered_tip.put(oav.mxsc.pin_tip.INVALID_POSITION)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    set_sim_value(smargon.x.readback, 0)

    def set_pin_tip_when_x_moved(*args, **kwargs):
        oav.mxsc.pin_tip.tip_x.sim_put(100)
        oav.mxsc.pin_tip.tip_y.sim_put(200)

    smargon.x.set = MagicMock(side_effect=set_pin_tip_when_x_moved)

    result = RE(move_pin_into_view(oav, smargon))

    assert await smargon.x.readback.get_value() == DEFAULT_STEP_SIZE
    assert result.plan_result == (100, 200)


def test_given_tip_at_zero_but_will_be_found_when_get_tip_into_view_then_smargon_moved_negative_and_tip_returned(
    oav: OAV,
    RE: RunEngine,
    smargon: Smargon,
):
    smargon.x_low_lim.user_setpoint.sim_set_limits([-2, 2])
    oav.mxsc.pin_tip.tip_x.sim_put(0)
    oav.mxsc.pin_tip.tip_y.sim_put(100)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    smargon.x.user_readback.sim_put(0)

    def set_pin_tip_when_x_moved(*args, **kwargs):
        oav.mxsc.pin_tip.tip_x.sim_put(100)
        oav.mxsc.pin_tip.tip_y.sim_put(200)

    smargon.x.subscribe(set_pin_tip_when_x_moved, run=False)

    result = RE(move_pin_into_view(oav, smargon))

    assert smargon.x.user_readback.get() == -DEFAULT_STEP_SIZE
    assert result.plan_result == (100, 200)


def test_pin_tip_starting_near_negative_edge_doesnt_exceed_limit(
    oav: OAV,
    RE: RunEngine,
    smargon: Smargon,
):
    smargon.x.user_setpoint.sim_set_limits([-2, 2])
    smargon.x.user_setpoint.sim_put(-1.8)
    smargon.x.user_readback.sim_put(-1.8)
    oav.mxsc.pin_tip.tip_x.sim_put(0)
    oav.mxsc.pin_tip.tip_y.sim_put(100)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(oav, smargon, max_steps=1))

    assert smargon.x.user_readback.get() == -2


def test_pin_tip_starting_near_positive_edge_doesnt_exceed_limit(
    smargon: Smargon, oav: OAV, RE: RunEngine
):
    smargon.x.user_setpoint.sim_set_limits([-2, 2])
    smargon.x.user_setpoint.sim_put(1.8)
    smargon.x.user_readback.sim_put(1.8)
    oav.mxsc.pin_tip.tip_x.sim_put(-1)
    oav.mxsc.pin_tip.tip_y.sim_put(-1)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(oav, smargon, max_steps=1))

    assert smargon.x.user_readback.get() == 2


def test_given_no_tip_found_ever_when_get_tip_into_view_then_smargon_moved_positive_and_exception_thrown(
    smargon: Smargon, oav: OAV, RE: RunEngine
):
    smargon.x.user_setpoint.sim_set_limits([-2, 2])
    oav.mxsc.pin_tip.triggered_tip.put(oav.mxsc.pin_tip.INVALID_POSITION)
    oav.mxsc.pin_tip.validity_timeout.put(0.01)

    smargon.x.user_readback.sim_put(0)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(oav, smargon))

    assert smargon.x.user_readback.get() == 1


def test_given_moving_out_of_range_when_move_with_warn_called_then_warning_exception(
    RE: RunEngine, smargon: Smargon
):
    smargon.x.high_limit_travel.sim_put(10)

    with pytest.raises(WarningException):
        RE(move_smargon_warn_on_out_of_range(smargon, (100, 0, 0)))


def return_pixel(pixel, *args):
    yield from null()
    return pixel


@patch(
    "hyperion.experiment_plans.pin_tip_centring_plan.wait_for_tip_to_be_found",
    new=partial(return_pixel, (200, 200)),
)
@patch(
    "hyperion.experiment_plans.pin_tip_centring_plan.get_move_required_so_that_beam_is_at_pixel",
    autospec=True,
)
@patch(
    "hyperion.experiment_plans.pin_tip_centring_plan.move_pin_into_view",
    new=partial(return_pixel, (100, 100)),
)
@patch(
    "hyperion.experiment_plans.pin_tip_centring_plan.pre_centring_setup_oav",
    autospec=True,
)
@patch("hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep", autospec=True)
@patch(
    "hyperion.experiment_plans.pin_tip_centring_plan.move_smargon_warn_on_out_of_range",
    autospec=True,
)
def test_when_pin_tip_centre_plan_called_then_expected_plans_called(
    move_smargon,
    mock_sleep,
    mock_setup_oav,
    get_move: MagicMock,
    smargon: Smargon,
    test_config_files,
    RE,
):
    smargon.omega.user_readback.sim_put(0)
    composite = PinTipCentringComposite(
        backlight=MagicMock(), oav=MagicMock(), smargon=smargon
    )
    RE(pin_tip_centre_plan(composite, 50, test_config_files))

    mock_setup_oav.assert_called_once()

    assert len(get_move.call_args_list) == 2

    args, _ = get_move.call_args_list[0]
    assert args[1] == (117, 100)

    assert smargon.omega.user_readback.get() == 90

    args, _ = get_move.call_args_list[1]
    assert args[1] == (217, 200)
