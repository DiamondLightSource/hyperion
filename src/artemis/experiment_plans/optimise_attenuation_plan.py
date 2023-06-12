import bluesky.plan_stubs as bps
from dodal.beamlines import i03
from dodal.devices.attenuator.attenuator import Attenuator
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini
from dodal.devices.zebra import Zebra

from artemis.log import LOGGER
from artemis.parameters import beamline_parameters
from artemis.parameters.beamline_parameters import (
    get_beamline_parameters,
    get_beamline_prefixes,
)


class PlaceholderParams:
    """placeholder for the actual params needed for this function"""

    @classmethod
    def from_beamline_params(cls, params):
        return (
            params["attenuation_optimisation_type"],  # optimisation type,
            params["fluorescence_attenuation_low_roi"],  # low_roi,
            params["fluorescence_attenuation_high_roi"],  # high_roi
            params["attenuation_optimisation_start_transmission"],  # transmission
            params["attenuation_optimisation_target_count"],  # target
            params["attenuation_optimisation_lower_limit"],  # lower limit
            params["attenuation_optimisation_upper_limit"],  # upper limit
            params["attenuation_optimisation_optimisation_cycles"],  # max cycles
            params["attenuation_optimisation_multiplier"],  # increment
        )


def create_devices():
    i03.zebra()
    i03.xspress3mini()
    i03.attenuator()


def optimise_attenuation_plan(
    collection_time,  # not sure what type this is, comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    params: beamline_parameters,
    xspress3mini: Xspress3Mini,
    zebra: Zebra,
    attenuator: Attenuator,
    low_roi=0,
    high_roi=0,
):
    """Do the attenuation optimisation using count threshold"""

    # Get parameters (placeholder for now). Should we get these within the device or plan?

    (
        optimisation_type,
        transmission,
        target,
        lower_limit,
        upper_limit,
        max_cycles,
        increment,
        default_low_roi,
        default_high_roi,
        # TODO make this a params dictionary instead?
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    # Zebra, xspress3mini, attenuator are all used for this. Right now the logic in xspress3_mini.py won't
    # work since the devices won't link in that way, so need to move that logic to a bluesky plan

    LOGGER.info("Starting Xspress3Mini optimisation routine")

    if low_roi == 0:
        low_roi = default_low_roi
    if high_roi == 0:
        high_roi = default_high_roi

    LOGGER.info(
        f"Optimisation will be performed across ROI channels {low_roi} - {high_roi}"
    )
    group = "setup"
    yield from bps.abs_set(xspress3mini.acquire_time, collection_time, group=group)

    if optimisation_type == "total_counts":
        LOGGER.info("Using total count optimisation")

    for cycle in range(0, max_cycles):
        LOGGER.info(
            f"Setting transmission to {transmission} for attenuation optimisation cycle {cycle}"
        )

        yield from bps.abs_set(
            attenuator.do_set_transmission, 1, group="set_transmission"
        )
        yield from bps.abs_set(
            xspress3mini.hdf_num_capture, 1
        )  # TODO: check when we should wait for this to complete

        # Arm xspress3mini
        yield from bps.abs_set(xspress3mini.do_arm, 1, wait=True)

        # Reset amd arm zebra

        data = xspress3mini.channel_1.lat
