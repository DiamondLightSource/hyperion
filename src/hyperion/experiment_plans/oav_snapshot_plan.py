import dataclasses
from datetime import datetime

from blueapi.core import BlueskyContext, MsgGenerator
from bluesky import plan_stubs as bps
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.smargon import Smargon

from hyperion.device_setup_plans.setup_oav import setup_general_oav_params
from hyperion.parameters.components import WithSnapshot
from hyperion.parameters.constants import DocDescriptorNames
from hyperion.utils.context import device_composite_from_context

OAV_SNAPSHOT_GROUP = "oav_snapshot_group"


@dataclasses.dataclass
class OavSnapshotComposite:
    smargon: Smargon
    oav: OAV


def create_devices(context: BlueskyContext) -> OavSnapshotComposite:
    return device_composite_from_context(context, OavSnapshotComposite)  # type: ignore


def _setup_oav(
    composite: OavSnapshotComposite,
    parameters: WithSnapshot,
    oav_parameters: OAVParameters,
):
    yield from setup_general_oav_params(composite.oav, oav_parameters)
    yield from bps.abs_set(
        composite.oav.snapshot.directory, str(parameters.snapshot_directory)
    )


def _take_oav_snapshot(
    composite: OavSnapshotComposite, parameters: WithSnapshot, omega: float
):
    yield from bps.abs_set(composite.smargon.omega, omega, group=OAV_SNAPSHOT_GROUP)
    time_now = datetime.now()
    filename = f"{time_now.strftime('%H%M%S')}_oav_snapshot_{omega:.0f}"
    yield from bps.abs_set(composite.oav.snapshot.filename, filename)
    yield from bps.trigger(composite.oav.snapshot, group=OAV_SNAPSHOT_GROUP)
    yield from bps.wait(group=OAV_SNAPSHOT_GROUP)
    yield from bps.create(DocDescriptorNames.OAV_ROTATION_SNAPSHOT_TRIGGERED)
    yield from bps.read(composite.oav.snapshot)
    yield from bps.save()


def oav_snapshot_plan(
    composite: OavSnapshotComposite,
    parameters: WithSnapshot,
    oav_parameters: OAVParameters,
    wait: bool = True,
) -> MsgGenerator:
    omegas = parameters.snapshot_omegas_deg
    if not omegas:
        return
    yield from _setup_oav(composite, parameters, oav_parameters)
    for omega in omegas:
        yield from _take_oav_snapshot(composite, parameters, omega)
