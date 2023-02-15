import bluesky.plan_stubs as bps

from artemis.devices.zebra import (
    DISCONNECT,
    OR1,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_SHUTTER,
    TTL_XSPRESS3,
    Zebra,
)


def setup_zebra_for_rotation(
    zebra: Zebra, group="setup_zebra_for_rotation", wait=False
):
    # Need to:
    # Trigger the detector with a pulse, (pulse step set to exposure time?)
    # Trigger the shutter with the gate (from PC_GATE & SOFTIN1 -> OR1)
    # Set gate start to current angle +1
    # set gate width to total width

    yield from bps.abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1, group=group)
    yield from bps.abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT, group=group)
    yield from bps.abs_set(zebra.output.pulse_1_input, DISCONNECT, group=group)

    if wait:
        bps.wait(group)
