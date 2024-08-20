from datetime import datetime
from typing import Protocol

from blueapi.core import MsgGenerator
from bluesky import plan_stubs as bps
from dodal.devices.aperturescatterguard import AperturePosition, ApertureScatterguard
from dodal.devices.backlight import Backlight, BacklightPosition
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon
from mx_bluesky.parameters import WithSnapshot

from hyperion.device_setup_plans.setup_oav import setup_general_oav_params
from hyperion.parameters.constants import DocDescriptorNames

OAV_SNAPSHOT_SETUP_GROUP = "oav_snapshot_setup"
OAV_SNAPSHOT_SETUP_SHOT = "oav_snapshot_setup_shot"
OAV_SNAPSHOT_GROUP = "oav_snapshot_group"


class OavSnapshotComposite(Protocol):
    smargon: Smargon
    oav: OAV
    aperture_scatterguard: ApertureScatterguard
    backlight: Backlight


def setup_oav_snapshot_plan(
    composite: OavSnapshotComposite,
    parameters: WithSnapshot,
    max_omega_velocity_deg_s: float,
):
    if not parameters.take_snapshots:
        return

    yield from bps.abs_set(
        composite.smargon.omega.velocity, max_omega_velocity_deg_s, wait=True
    )
    yield from bps.abs_set(
        composite.backlight, BacklightPosition.IN, group=OAV_SNAPSHOT_SETUP_GROUP
    )
    yield from bps.abs_set(
        composite.aperture_scatterguard,
        AperturePosition.ROBOT_LOAD,
        group=OAV_SNAPSHOT_SETUP_GROUP,
    )


def oav_snapshot_plan(
    composite: OavSnapshotComposite,
    parameters: WithSnapshot,
    oav_parameters: OAVParameters,
    wait: bool = True,
) -> MsgGenerator:
    if not parameters.take_snapshots:
        return
    yield from bps.wait(group=OAV_SNAPSHOT_SETUP_GROUP)
    yield from _setup_oav(composite, parameters, oav_parameters)
    for omega in parameters.snapshot_omegas_deg or []:
        yield from _take_oav_snapshot(composite, omega)


def _setup_oav(
    composite: OavSnapshotComposite,
    parameters: WithSnapshot,
    oav_parameters: OAVParameters,
):
    yield from setup_general_oav_params(composite.oav, oav_parameters)
    yield from bps.abs_set(
        composite.oav.snapshot.directory, str(parameters.snapshot_directory)
    )


def _take_oav_snapshot(composite: OavSnapshotComposite, omega: float):
    yield from bps.abs_set(
        composite.smargon.omega, omega, group=OAV_SNAPSHOT_SETUP_SHOT
    )
    time_now = datetime.now()
    filename = f"{time_now.strftime('%H%M%S')}_oav_snapshot_{omega:.0f}"
    yield from bps.abs_set(
        composite.oav.snapshot.filename, filename, group=OAV_SNAPSHOT_SETUP_SHOT
    )
    yield from bps.wait(group=OAV_SNAPSHOT_SETUP_SHOT)
    yield from bps.trigger(composite.oav.snapshot, wait=True)
    yield from bps.create(DocDescriptorNames.OAV_ROTATION_SNAPSHOT_TRIGGERED)
    yield from bps.read(composite.oav.snapshot)
    yield from bps.save()
