from dodal.devices.smargon import Smargon
from dodal.devices.zebra import (
    # PC_ARM_SOURCE_SOFT,
    # PC_ARM_SOURCE_EXT,
    Zebra,
)
from bluesky import plan_stubs as bps
from bluesky.plans import grid_scan
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback


zebra = Zebra("BL03S-EA-ZEBRA-01:", name="zebra")
smargon = Smargon("BL03S", name="smargon")

smargon.wait_for_connection()
zebra.wait_for_connection()

RE = RunEngine({})

bec = BestEffortCallback()

# Send all metadata/data captured to the BestEffortCallback.
RE.subscribe(bec)


def take_reading(dets, name="primary"):
    print("take_reading")
    yield from bps.trigger_and_read(dets, name)


def move_per_step(step, pos_cache):
    print("move_per_step")
    yield from bps.move_per_step(step, pos_cache)


def do_at_each_step(detectors, step, pos_cache):
    motors = step.keys()
    yield from move_per_step(step, pos_cache)
    yield from take_reading(list(detectors) + list(motors))


def my_plan():
    # set up zebra
    # set up detector
    # do gridscan
    # yield from bps.mv(smargon.x, 20)
    # yield from bps.abs_set(zebra.pc.arm_source, PC_ARM_SOURCE_EXT)

    detectors = []  # zebra.pc.arm_source]
    grid_args = [smargon.y, 0, 40, 5, smargon.x, 0, 40, 5]

    yield from grid_scan(
        detectors, *grid_args, snake_axes=True, per_step=do_at_each_step, md={}
    )


RE(my_plan())
