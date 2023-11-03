"""Utility functions for the I03 PandA"""
from typing import Any, Dict, List

from ophyd_async.core import (
    SignalRW,
    get_signal_values,
    load_from_yaml,
    save_to_yaml,
    set_signal_values,
    walk_rw_signals,
)
from ophyd_async.panda import PandA


async def read_detector_output(panda: PandA):
    # In I03, the panda's TTLOUT1 goes to the Eiger and TTLOUT2 goes to the fast shutter
    return await panda.ttlout[1].val.read()[
        "value"
    ]  # can be ZERO, ONE, or linked to another PV


async def read_fast_shutter_output(panda: PandA):
    return await panda.ttlout[2].val.read()["value"]


def _get_panda_phases(panda: PandA):
    # Panda has two load phases. If the signal name ends in the string "UNITS", it needs to be loaded first so put in first phase
    signalRW_and_value = yield from get_signal_values(walk_rw_signals(panda))
    phase_1 = {}
    phase_2 = {}
    for signal_name in signalRW_and_value.keys():
        if signal_name[-5:] == "units":
            phase_1[signal_name] = signalRW_and_value[signal_name]
        else:
            phase_2[signal_name] = signalRW_and_value[signal_name]

    return [phase_1, phase_2]


def save_panda(panda: PandA):
    phases = yield from _get_panda_phases(panda)
    save_to_yaml(phases, "/scratch/qqh35939/panda_yaml_saves/test.yaml")


def load_panda(panda: PandA):
    phases = yield from _get_panda_phases(panda)
    values = load_from_yaml("/scratch/qqh35939/panda_yaml_saves/test.yaml")
    signals_to_set = walk_rw_signals(panda)
    yield from set_signal_values(signals_to_set, values)
