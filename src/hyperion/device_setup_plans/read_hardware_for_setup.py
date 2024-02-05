from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.DCM import DCM
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator

from hyperion.log import LOGGER
from hyperion.parameters.constants import (
    ISPYB_HARDWARE_READ_PLAN,
    ISPYB_TRANSMISSION_FLUX_READ_PLAN,
)


def read_hardware_for_ispyb_pre_collection(
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    aperture_scatterguard: ApertureScatterguard,
):
    LOGGER.info("Reading status of beamline parameters for ispyb deposition.")
    yield from bps.create(
        name=ISPYB_HARDWARE_READ_PLAN
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.current_gap)
    yield from bps.read(synchrotron.machine_status.synchrotron_mode)
    yield from bps.read(s4_slit_gaps.xgap)
    yield from bps.read(s4_slit_gaps.ygap)
    yield from bps.read(aperture_scatterguard.selected_aperture)
    yield from bps.save()


def read_hardware_for_ispyb_during_collection(
    attenuator: Attenuator, flux: Flux, dcm: DCM
):
    LOGGER.info("Reading status of beamline parameters for ispyb deposition.")
    yield from bps.create(name=ISPYB_TRANSMISSION_FLUX_READ_PLAN)
    yield from bps.read(attenuator.actual_transmission)
    yield from bps.read(flux.flux_reading)
    yield from bps.rd(dcm.energy_in_kev)
    yield from bps.save()
