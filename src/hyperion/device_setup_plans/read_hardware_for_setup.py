from __future__ import annotations

import bluesky.plan_stubs as bps
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.dcm import DCM
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from dodal.devices.robot import BartRobot
from dodal.devices.slits import Slits
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator

from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST


def read_hardware_for_ispyb_pre_collection(
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: Slits,
    aperture_scatterguard: ApertureScatterguard,
    robot: BartRobot,
):
    LOGGER.info("Reading status of beamline for ispyb deposition, pre collection.")
    yield from bps.create(
        name=CONST.DESCRIPTORS.ISPYB_HARDWARE_READ
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.current_gap)
    yield from bps.read(synchrotron.synchrotron_mode)
    yield from bps.read(s4_slit_gaps.x_gap)
    yield from bps.read(s4_slit_gaps.y_gap)
    yield from bps.read(aperture_scatterguard)
    yield from bps.save()


def read_hardware_for_ispyb_during_collection(
    attenuator: Attenuator,
    flux: Flux,
    dcm: DCM,
):
    LOGGER.info("Reading status of beamline for ispyb deposition, during collection.")
    yield from bps.create(name=CONST.DESCRIPTORS.ISPYB_TRANSMISSION_FLUX_READ)
    yield from bps.read(attenuator.actual_transmission)
    yield from bps.read(flux.flux_reading)
    yield from bps.read(dcm.energy_in_kev)
    yield from bps.save()


def read_hardware_for_nexus_writer(detector: EigerDetector):
    yield from bps.create(name=CONST.DESCRIPTORS.NEXUS_READ)
    yield from bps.read(detector.bit_depth)
    yield from bps.save()


def read_hardware_for_zocalo(detector: EigerDetector):
    yield from bps.create(name=CONST.DESCRIPTORS.ZOCALO_HW_READ)
    yield from bps.read(detector.odin.file_writer.id)
    yield from bps.save()
