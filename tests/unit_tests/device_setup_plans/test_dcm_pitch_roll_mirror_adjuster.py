from unittest.mock import MagicMock

from dodal.devices.DCM import DCM
from dodal.devices.hfm import HFM
from dodal.devices.i0 import I0
from dodal.devices.qbpm1 import QBPM1
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.vfm import VFM

from hyperion.device_setup_plans.dcm_pitch_roll_mirror_adjuster import (
    DCMPitchRollMirrorAdjuster,
)


def test_auto_adjust_dcm_hfm_vfm_pitch_roll(
    dcm: DCM, vfm: VFM, hfm: HFM, qbpm1: QBPM1, s4_slit_gaps: S4SlitGaps, i0: I0, sim
):
    peak_finder = MagicMock()
    peak_finder.find_peak_plan = sim.mock_message_generator("find_peak_plan")
    sim.add_handler(
        "read",
        "dcm_bragg_in_degrees",
        lambda msg: {"dcm_bragg_in_degrees": {"value": 3.0}},
    )

    generator = DCMPitchRollMirrorAdjuster(
        dcm, vfm, hfm, qbpm1, s4_slit_gaps, i0, peak_finder
    ).auto_adjust_dcm_hfm_vfm_pitch_roll()

    messages = sim.simulate_plan(generator)

    messages = sim.assert_message_and_return_remaining(
        messages,
        lambda msg: msg.command == "find_peak_plan"
        and msg.args
        == (
            dcm.pitch,
            qbpm1.intensityC,
            0,
            0.075,
            0.002,
        ),
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "sleep" and msg.args == (2,)
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "dcm_roll_in_mrad"
        and msg.args == (1.5,),
        "prepare_for_vfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "hfm_fine_pitch_mm"
        and msg.args == (0.017,),
        "prepare_for_vfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "vfm_fine_pitch_mm"
        and msg.args == (0.019,),
        "prepare_for_vfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_xgap"
        and msg.args == (500,),
        "prepare_for_vfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_ygap"
        and msg.args == (60,),
        "prepare_for_vfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "wait", "prepare_for_vfm_align"
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "find_peak_plan"
        and msg.args
        == (
            vfm.fine_pitch_mm,
            i0.intensity,
            0.019,
            0.012,
            0.0006,
        ),
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_xgap"
        and msg.args == (100,),
        "prepare_for_hfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_ygap"
        and msg.args == (60,),
        "prepare_for_hfm_align",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "wait", "prepare_for_hfm_align"
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "find_peak_plan"
        and msg.args
        == (
            hfm.fine_pitch_mm,
            i0.intensity,
            0.017,
            0.016,
            0.0006,
        ),
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_xgap"
        and msg.args == (500,),
        "reset_slit_gap",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj
        and msg.obj.name == "s4_slit_gaps_ygap"
        and msg.args == (500,),
        "reset_slit_gap",
    )
    messages = sim.assert_message_and_return_remaining(
        messages[1:], lambda msg: msg.command == "wait", "reset_slit_gap"
    )
