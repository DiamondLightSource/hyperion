from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.beamlines.i03 import Attenuator, Flux, S4SlitGaps, Synchrotron, Undulator

import hyperion.log
from hyperion.parameters.constants import (
    ISPYB_HARDWARE_READ_PLAN,
    ISPYB_TRANSMISSION_FLUX_READ_PLAN,
)


def read_hardware_for_ispyb_pre_collection(
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
):
    hyperion.log.LOGGER.info(
        "Reading status of beamline parameters for ispyb deposition."
    )
    yield from bps.create(
        name=ISPYB_HARDWARE_READ_PLAN
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.current_gap)
    yield from bps.read(synchrotron.machine_status.synchrotron_mode)
    yield from bps.read(s4_slit_gaps.xgap)
    yield from bps.read(s4_slit_gaps.ygap)
    yield from bps.save()


def read_hardware_for_ispyb_during_collection(attenuator: Attenuator, flux: Flux):
    hyperion.log.LOGGER.info(
        "Reading status of beamline parameters for ispyb deposition."
    )
    yield from bps.create(name=ISPYB_TRANSMISSION_FLUX_READ_PLAN)
    yield from bps.read(attenuator.actual_transmission)
    yield from bps.read(flux.flux_reading)
    yield from bps.save()
