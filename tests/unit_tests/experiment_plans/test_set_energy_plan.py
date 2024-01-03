from unittest.mock import patch

from bluesky.utils import Msg

from hyperion.experiment_plans.set_energy_plan import (
    SetEnergyComposite,
    set_energy_plan,
)
from hyperion.parameters.plan_specific.set_energy_internal_params import (
    SetEnergyInternalParameters,
)


@patch(
    "hyperion.experiment_plans.set_energy_plan.dcm_pitch_roll_mirror_adjuster.adjust_dcm_pitch_roll_vfm_from_lut",
    return_value=iter([Msg("adjust_dcm_pitch_roll_vfm_from_lut")]),
)
def test_set_energy_plan(
    mock_dcm_pra,
    dcm,
    vfm,
    vfm_mirror_voltages,
    beamline_parameters,
    xbpm_feedback,
    attenuator,
    undulator_dcm,
    sim_run_engine,
):
    composite = SetEnergyComposite(
        vfm,
        vfm_mirror_voltages,
        dcm,
        undulator_dcm,
        xbpm_feedback,
        attenuator,
    )
    internal_params = SetEnergyInternalParameters()
    messages = sim_run_engine.simulate_plan(
        set_energy_plan(11.1, composite, internal_params)
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages,
        lambda msg: msg.command == "set"
        and msg.obj.name == "xbpm_feedback_pause_feedback"
        and msg.args == (0,),
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "attenuator"
        and msg.args == (0.1,),
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "undulator_dcm"
        and msg.args == (11.1,)
        and msg.kwargs["group"] == "UNDULATOR_GROUP",
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "adjust_dcm_pitch_roll_vfm_from_lut"
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "wait" and msg.kwargs["group"] == "UNDULATOR_GROUP",
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "xbpm_feedback_pause_feedback"
        and msg.args == (1,),
    )
    messages = sim_run_engine.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "attenuator"
        and msg.args == (1.0,),
    )
