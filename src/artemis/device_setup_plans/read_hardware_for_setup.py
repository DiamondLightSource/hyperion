from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.beamlines.i03 import Flux, S4SlitGaps, Synchrotron, Undulator

import artemis.log
from artemis.parameters.constants import ISPYB_PLAN_NAME


def read_hardware_for_ispyb(
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    flux: Flux,
):
    artemis.log.LOGGER.info(
        "Reading status of beamline parameters for ispyb deposition."
    )
    yield from bps.create(
        name=ISPYB_PLAN_NAME
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.gap)
    yield from bps.read(synchrotron.machine_status.synchrotron_mode)
    yield from bps.read(s4_slit_gaps.xgap)
    yield from bps.read(s4_slit_gaps.ygap)
    yield from bps.read(flux.flux_reading)
    yield from bps.save()
