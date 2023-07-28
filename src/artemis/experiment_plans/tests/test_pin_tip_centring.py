from functools import partial
from unittest.mock import MagicMock, patch

import pytest
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.smargon import Smargon
from ophyd.sim import make_fake_device

from artemis.exceptions import WarningException
from artemis.experiment_plans.pin_tip_centring_plan import (
    create_devices,
    move_pin_into_view,
    move_smargon_warn_on_out_of_range,
    pin_tip_centre_plan,
)


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


def test_given_moving_out_of_range_when_move_with_warn_called_then_warning_exception(
    RE: RunEngine,
):
    fake_smargon = make_fake_device(Smargon)(name="")
    fake_smargon.x.user_setpoint.sim_set_limits([0, 10])

    with pytest.raises(WarningException):
        RE(move_smargon_warn_on_out_of_range(fake_smargon, (100, 0, 0)))


@patch("artemis.experiment_plans.pin_tip_centring_plan.i03", autospec=True)
def test_when_create_devices_called_then_devices_created(mock_i03):
    create_devices()
    mock_i03.oav.assert_called_once()
    mock_i03.smargon.assert_called_once()
    mock_i03.backlight.assert_called_once()


def return_pixel(pixel, *args):
    yield from null()
    return pixel


@patch(
    "artemis.experiment_plans.pin_tip_centring_plan.wait_for_tip_to_be_found",
    new=partial(return_pixel, (200, 200)),
)
@patch(
    "artemis.experiment_plans.pin_tip_centring_plan.get_move_required_so_that_beam_is_at_pixel",
    autospec=True,
)
@patch(
    "artemis.experiment_plans.pin_tip_centring_plan.move_pin_into_view",
    new=partial(return_pixel, (100, 100)),
)
@patch(
    "artemis.experiment_plans.pin_tip_centring_plan.pre_centring_setup_oav",
    autospec=True,
)
@patch("artemis.experiment_plans.pin_tip_centring_plan.i03", autospec=True)
@patch("artemis.experiment_plans.pin_tip_centring_plan.bps.sleep", autospec=True)
@patch(
    "artemis.experiment_plans.pin_tip_centring_plan.move_smargon_warn_on_out_of_range",
    autospec=True,
)
def test_when_pin_tip_centre_plan_called_then_expected_plans_called(
    move_smargon,
    mock_sleep,
    mock_i03,
    mock_setup_oav,
    get_move: MagicMock,
    smargon: Smargon,
    test_config_files,
    RE,
):
    mock_i03.smargon.return_value = smargon
    smargon.omega.user_readback.sim_put(0)
    RE(pin_tip_centre_plan(50, test_config_files))

    mock_setup_oav.assert_called_once()

    assert len(get_move.call_args_list) == 2

    args, _ = get_move.call_args_list[0]
    assert args[1] == (117, 100)

    assert smargon.omega.user_readback.get() == 90

    args, _ = get_move.call_args_list[1]
    assert args[1] == (217, 200)
