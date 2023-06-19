import bluesky.plan_stubs as bps
import numpy as np
from dodal.beamlines import i03
from dodal.devices.attenuator.attenuator import Attenuator
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini
from dodal.devices.zebra import Zebra

from artemis.device_setup_plans.setup_zebra import arm_zebra
from artemis.log import LOGGER
from artemis.parameters import beamline_parameters
from artemis.parameters.beamline_parameters import get_beamline_parameters


class AttenuationOptimisationFailedException(Exception):
    pass


class PlaceholderParams:
    """placeholder for the actual params needed for this function"""

    @classmethod
    def from_beamline_params(cls, params):
        return (
            params["attenuation_optimisation_type"],  # optimisation type,
            int(params["fluorescence_attenuation_low_roi"]),  # low_roi,
            int(params["fluorescence_attenuation_high_roi"]),  # high_roi
            params["attenuation_optimisation_start_transmission"] / 100,  # transmission
            params["attenuation_optimisation_target_count"] * 10,  # target
            params["attenuation_optimisation_lower_limit"],  # lower limit
            params["attenuation_optimisation_upper_limit"],  # upper limit
            int(params["attenuation_optimisation_optimisation_cycles"]),  # max cycles
            params["attenuation_optimisation_multiplier"],  # increment
        )


def create_devices():
    i03.zebra()
    i03.xspress3mini()
    i03.attenuator()


def total_counts_optimisation(
    max_cycles,
    transmission,
    attenuator,
    xspress3mini,
    zebra,
    low_roi,
    high_roi,
    lower_limit,
    upper_limit,
    target_count,
):
    LOGGER.info("Using total count optimisation")

    for cycle in range(0, max_cycles):
        LOGGER.info(
            f"Setting transmission to {transmission} for attenuation optimisation cycle {cycle}"
        )

        yield from bps.abs_set(
            attenuator.do_set_transmission,
            transmission,
            group="set_transmission",
        )

        yield from bps.abs_set(xspress3mini.set_num_images, 1, wait=True)

        # Arm xspress3mini
        yield from bps.abs_set(xspress3mini.do_arm, 1, group="xsarm")
        LOGGER.info("Arming Zebra")
        LOGGER.debug("Resetting Zebra")
        yield from bps.abs_set(zebra.pc.reset, 1, group="reset_zebra")
        yield from bps.wait(
            group="xsarm"
        )  # TODO test this also waits for acquire status
        LOGGER.info("Arming Xspress3Mini complete")

        yield from arm_zebra(zebra)

        data = np.array((yield from bps.rd(xspress3mini.dt_corrected_latest_mca)))
        total_count = sum(data[int(low_roi) : int(high_roi)])
        LOGGER.info(f"Total count is {total_count}")
        if lower_limit <= total_count <= upper_limit:
            optimised_transmission = transmission
            LOGGER.info(
                f"Total count is within accepted limits: {lower_limit}, {total_count}, {upper_limit}"
            )
            break

        transmission = (target_count / (total_count)) * transmission

        if cycle == max_cycles - 1:
            raise AttenuationOptimisationFailedException(
                f"Unable to optimise attenuation after maximum cycles.\
                                                            Total count is not within limits: {lower_limit} <= {total_count}\
                                                                <= {upper_limit}"
            )

    return optimised_transmission


def check_parameters(
    target, upper_limit, lower_limit, default_high_roi, default_low_roi
):
    if target < lower_limit or target > upper_limit:
        raise (
            ValueError(
                f"Target {target} is outside of lower and upper bounds: {lower_limit} to {upper_limit}"
            )
        )

    if upper_limit < lower_limit:
        raise ValueError(
            f"Upper limit {upper_limit} must be greater than lower limit {lower_limit}"
        )
        # TODO test these exceptions

    if default_high_roi < default_low_roi:
        raise ValueError(
            f"Upper roi {default_high_roi} must be greater than lower roi {default_low_roi}"
        )


def optimise_attenuation_plan(
    collection_time,  # Comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    params: beamline_parameters,
    xspress3mini: Xspress3Mini,
    zebra: Zebra,
    attenuator: Attenuator,
    low_roi=None,
    high_roi=None,
):
    (
        optimisation_type,
        default_low_roi,
        default_high_roi,
        initial_transmission,
        target,
        lower_limit,
        upper_limit,
        max_cycles,
        increment,
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    check_parameters(
        target, upper_limit, lower_limit, default_high_roi, default_low_roi
    )

    # Hardcode these to make more sense
    upper_limit = 4000
    lower_limit = 2000
    target = 3000

    # GDA params currently sets them to 0 by default
    if low_roi is None or low_roi == 0:
        low_roi = default_low_roi
    if high_roi is None or high_roi == 0:
        high_roi = default_high_roi

    # Hardcode this for now:
    optimisation_type = "total_counts"

    yield from bps.abs_set(
        xspress3mini.acquire_time, collection_time, wait=True
    )  # Don't necessarily need to wait here

    # Do the attenuation optimisation using count threshold
    if optimisation_type == "total_counts":
        LOGGER.info(
            f"Starting Xspress3Mini optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )

        return (
            yield from total_counts_optimisation(
                max_cycles,
                initial_transmission,
                attenuator,
                xspress3mini,
                zebra,
                low_roi,
                high_roi,
                lower_limit,
                upper_limit,
                target,
            )
        )
