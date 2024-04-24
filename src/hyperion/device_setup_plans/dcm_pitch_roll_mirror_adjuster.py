import json

import bluesky.plan_stubs as bps
from dodal.devices.DCM import DCM
from dodal.devices.focusing_mirror import (
    FocusingMirrorWithStripes,
    MirrorStripe,
    VFMMirrorVoltages,
)
from dodal.devices.util.adjuster_plans import lookup_table_adjuster
from dodal.devices.util.lookup_tables import (
    linear_interpolation_lut,
)

from hyperion.log import LOGGER

MIRROR_VOLTAGE_GROUP = "MIRROR_VOLTAGE_GROUP"
DCM_GROUP = "DCM_GROUP"


def _apply_and_wait_for_voltages_to_settle(
    stripe: MirrorStripe,
    mirror: FocusingMirrorWithStripes,
    mirror_voltages: VFMMirrorVoltages,
):
    with open(mirror_voltages.voltage_lookup_table_path) as lut_file:
        json_obj = json.load(lut_file)

    # sample mode is the only mode supported
    sample_data = json_obj["sample"]
    mirror_key = mirror.name.lower()
    if stripe == MirrorStripe.BARE:
        stripe_key = "bare"
    elif stripe == MirrorStripe.RHODIUM:
        stripe_key = "rh"
    elif stripe == MirrorStripe.PLATINUM:
        stripe_key = "pt"
    else:
        raise ValueError(f"Unsupported stripe '{stripe}'")

    required_voltages = sample_data[stripe_key][mirror_key]
    for voltage_channel, required_voltage in zip(
        mirror_voltages.voltage_channels, required_voltages
    ):
        LOGGER.debug(
            f"Applying and waiting for voltage {voltage_channel.name} = {required_voltage}"
        )
        yield from bps.abs_set(
            voltage_channel, required_voltage, group=MIRROR_VOLTAGE_GROUP
        )

    yield from bps.wait(group=MIRROR_VOLTAGE_GROUP)


def adjust_mirror_stripe(
    energy_kev, mirror: FocusingMirrorWithStripes, mirror_voltages: VFMMirrorVoltages
):
    """Feedback should be OFF prior to entry, in order to prevent
    feedback from making unnecessary corrections while beam is being adjusted."""
    stripe = mirror.energy_to_stripe(energy_kev)

    LOGGER.info(
        f"Adjusting mirror stripe for {energy_kev}keV selecting {stripe} stripe"
    )
    yield from bps.abs_set(mirror.stripe, stripe, wait=True)
    yield from bps.abs_set(mirror.apply_stripe, 1)

    LOGGER.info("Adjusting mirror voltages...")
    yield from _apply_and_wait_for_voltages_to_settle(stripe, mirror, mirror_voltages)


def adjust_dcm_pitch_roll_vfm_from_lut(
    dcm: DCM,
    vfm: FocusingMirrorWithStripes,
    vfm_mirror_voltages: VFMMirrorVoltages,
    energy_kev,
):
    """Beamline energy-change post-adjustments : Adjust DCM and VFM directly from lookup tables.
    Lookups are performed against the Bragg angle which will have been automatically set by EPICS as a side-effect of the
    energy change prior to calling this function.
    Feedback should be OFF prior to entry, in order to prevent
    feedback from making unnecessary corrections while beam is being adjusted."""

    # DCM Pitch
    LOGGER.info(f"Adjusting DCM and VFM for {energy_kev} keV")
    bragg_deg = yield from bps.rd(dcm.bragg_in_degrees.user_readback)
    LOGGER.info(f"Read Bragg angle = {bragg_deg} degrees")
    dcm_pitch_adjuster = lookup_table_adjuster(
        linear_interpolation_lut(dcm.dcm_pitch_converter_lookup_table_path),
        dcm.pitch_in_mrad,
        bragg_deg,
    )
    yield from dcm_pitch_adjuster(DCM_GROUP)
    # It's possible we can remove these waits but we need to check
    LOGGER.info("Waiting for DCM pitch adjust to complete...")

    # DCM Roll
    dcm_roll_adjuster = lookup_table_adjuster(
        linear_interpolation_lut(dcm.dcm_roll_converter_lookup_table_path),
        dcm.roll_in_mrad,
        bragg_deg,
    )
    yield from dcm_roll_adjuster(DCM_GROUP)
    LOGGER.info("Waiting for DCM roll adjust to complete...")

    # DCM Perp pitch
    offset_mm = dcm.fixed_offset_mm
    LOGGER.info(f"Adjusting DCM offset to {offset_mm} mm")
    yield from bps.abs_set(dcm.offset_in_mm, offset_mm, group=DCM_GROUP)

    #
    # Adjust mirrors
    #

    # No need to change HFM

    # Assumption is focus mode is already set to "sample"
    # not sure how we check this

    # VFM Stripe selection
    yield from adjust_mirror_stripe(energy_kev, vfm, vfm_mirror_voltages)
    yield from bps.wait(DCM_GROUP)

    # VFM Adjust - for I03 this table always returns the same value
    assert (vfm_lut := vfm.bragg_to_lat_lookup_table_path) is not None
    vfm_x_adjuster = lookup_table_adjuster(
        linear_interpolation_lut(vfm_lut),
        vfm.x_mm,
        bragg_deg,
    )
    LOGGER.info("Waiting for VFM Lat (Horizontal Translation) to complete...")
    yield from vfm_x_adjuster()
