from bluesky.plan_stubs import abs_set

from artemis.devices.zebra import (
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


def setup_zebra_for_fgs(zebra: Zebra):
    yield from abs_set(zebra.output.out_pvs[TTL_DETECTOR], IN3_TTL)
    yield from abs_set(zebra.output.out_pvs[TTL_SHUTTER], IN4_TTL)
    yield from abs_set(zebra.output.out_pvs[TTL_XSPRESS3], DISCONNECT)
    yield from abs_set(zebra.output.pulse_1_input, DISCONNECT)


def set_zebra_shutter_to_manual(zebra: Zebra):
    yield from abs_set(zebra.output.out_pvs[TTL_DETECTOR], PC_PULSE)
    yield from abs_set(zebra.output.out_pvs[TTL_SHUTTER], OR1)
