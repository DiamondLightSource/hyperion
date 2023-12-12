from unittest.mock import MagicMock, patch

import pytest
from bluesky import RunEngine
from dodal.devices.DCM import DCM
from dodal.devices.focusing_mirror import (
    DEMAND_ACCEPTED_OK,
    FocusingMirror,
    MirrorStripe,
    VFMMirrorVoltages,
)
from ophyd import EpicsSignal
from ophyd.sim import NullStatus

from hyperion.device_setup_plans import dcm_pitch_roll_mirror_adjuster
from hyperion.device_setup_plans.dcm_pitch_roll_mirror_adjuster import (
    adjust_dcm_pitch_roll_vfm_from_lut,
    adjust_mirror_stripe,
)
from hyperion.parameters.beamline_parameters import GDABeamlineParameters


def test_apply_and_wait_for_voltages_to_settle_happy_path(
    vfm_mirror_voltages: VFMMirrorVoltages, vfm: FocusingMirror, RE: RunEngine
):
    _all_demands_accepted(vfm_mirror_voltages)

    RE(
        dcm_pitch_roll_mirror_adjuster._apply_and_wait_for_voltages_to_settle(
            MirrorStripe.BARE, vfm, vfm_mirror_voltages
        )
    )

    for channel, expected_voltage in zip(
        vfm_mirror_voltages.voltage_channels, [140, 100, 70, 30, 30, -65, 24, 15]
    ):
        channel._setpoint_v.set.assert_called_once_with(expected_voltage)


def _all_demands_accepted(vfm_mirror_voltages):
    for channel in vfm_mirror_voltages.voltage_channels:
        _mock_voltage_channel(channel._setpoint_v, channel._demand_accepted)


@patch("dodal.devices.focusing_mirror.DEFAULT_SETTLE_TIME_S", 3)
def test_apply_and_wait_for_voltages_to_settle_timeout(
    vfm_mirror_voltages: VFMMirrorVoltages, vfm: FocusingMirror, RE: RunEngine
):
    vfm_mirror_voltages.voltage_lookup_table_path = (
        "tests/test_data/test_mirror_focus.json"
    )
    vfm_mirror_voltages._channel14_voltage_device._setpoint_v.set = MagicMock()
    vfm_mirror_voltages._channel14_voltage_device._setpoint_v.set.return_value = (
        NullStatus()
    )
    vfm_mirror_voltages._channel14_voltage_device._demand_accepted.sim_put(0)
    for channel in vfm_mirror_voltages.voltage_channels[1:]:
        _mock_voltage_channel(
            channel._setpoint_v,
            channel._demand_accepted,
        )

    actual_exception = None

    try:
        RE(
            dcm_pitch_roll_mirror_adjuster._apply_and_wait_for_voltages_to_settle(
                MirrorStripe.BARE, vfm, vfm_mirror_voltages
            )
        )
    except Exception as e:
        actual_exception = e

    assert actual_exception is not None
    # Check that all voltages set in parallel
    for channel, expected_voltage in zip(
        vfm_mirror_voltages.voltage_channels, [140, 100, 70, 30, 30, -65, 24, 15]
    ):
        channel._setpoint_v.set.assert_called_once_with(expected_voltage)


def _mock_voltage_channel(setpoint: EpicsSignal, demand_accepted: EpicsSignal):
    def set_demand_and_return_ok(_):
        demand_accepted.sim_put(DEMAND_ACCEPTED_OK)
        return NullStatus()

    setpoint.set = MagicMock(side_effect=set_demand_and_return_ok)


mirror_stripe_params = [
    (6.999, "Bare", 140, 15),
    (7.001, "Rhodium", 124, -46),
]


@pytest.mark.parametrize(
    "energy_kev, expected_stripe, first_voltage, last_voltage", mirror_stripe_params
)
def test_adjust_mirror_stripe(
    vfm_mirror_voltages: VFMMirrorVoltages,
    vfm: FocusingMirror,
    RE: RunEngine,
    energy_kev,
    expected_stripe,
    first_voltage,
    last_voltage,
):
    _all_demands_accepted(vfm_mirror_voltages)
    vfm.stripe.set = MagicMock(return_value=NullStatus())
    vfm.apply_stripe.set = MagicMock()
    parent = MagicMock()
    parent.attach_mock(vfm.stripe.set, "stripe_set")
    parent.attach_mock(vfm.apply_stripe.set, "apply_stripe")

    RE(adjust_mirror_stripe(energy_kev, vfm, vfm_mirror_voltages))

    assert parent.method_calls[0] == ("stripe_set", (expected_stripe,))
    assert parent.method_calls[1] == ("apply_stripe", (1,))
    vfm_mirror_voltages._channel14_voltage_device._setpoint_v.set.assert_called_once_with(
        first_voltage
    )
    vfm_mirror_voltages._channel21_voltage_device._setpoint_v.set.assert_called_once_with(
        last_voltage
    )


def test_adjust_dcm_pitch_roll_vfm_from_lut(
    dcm: DCM,
    vfm: FocusingMirror,
    vfm_mirror_voltages: VFMMirrorVoltages,
    beamline_parameters: GDABeamlineParameters,
    sim,
):
    sim.add_handler_for_callback_subscribes()
    sim.add_handler(
        "read",
        "dcm_bragg_in_degrees",
        lambda msg: {"dcm_bragg_in_degrees": {"value": 5.0}},
    )

    messages = sim.simulate_plan(
        adjust_dcm_pitch_roll_vfm_from_lut(
            dcm, vfm, vfm_mirror_voltages, beamline_parameters, 7.5
        )
    )

    messages = sim.assert_message_and_return_remaining(
        messages,
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm_pitch_in_mrad"
        and abs(msg.args[0] - -0.75859) < 1e-5
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm_roll_in_mrad"
        and abs(msg.args[0] - 4.0) < 1e-5
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm_offset_in_mm"
        and msg.args == (25.6,)
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "vfm_stripe"
        and msg.args == ("Rhodium",),
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "wait",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "vfm_apply_stripe"
        and msg.args == (1,),
    )
    for channel, expected_voltage in (
        (14, 124),
        (15, 114),
        (16, 34),
        (17, 49),
        (18, 19),
        (19, -116),
        (20, 4),
        (21, -46),
    ):
        messages = sim.assert_message_and_return_remaining(
            messages[1:],
            lambda msg: msg.command == "set"
            and msg.obj.name == f"vfm_mirror_voltages__channel{channel}_voltage_device"
            and msg.args == (expected_voltage,),
        )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "wait" and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "vfm_lat_mm"
        and msg.args == (10.0,),
    )
