import bluesky.plan_stubs as bps
from dodal.devices.zebra import (
    DISCONNECT,
    IN3_TTL,
    IN4_TTL,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    Zebra,
)


def setup_zebra_for_stepped_grid_scan(
    zebra: Zebra, group="setup_zebra_for_stepped_grid_scan", wait=False
):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], IN3_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], IN4_TTL, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1_input, DISCONNECT, group=group)
    if wait:
        bps.wait(group)


def set_zebra_shutter_to_manual(
    zebra: Zebra, group="set_zebra_shutter_to_manual", wait=False
):
    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)
    if wait:
        bps.wait(group)
