from enum import Enum

import bluesky.plan_stubs as bps
import numpy as np
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini
from dodal.devices.zebra import Zebra

from artemis.device_setup_plans.setup_zebra import arm_zebra
from artemis.log import LOGGER
from artemis.parameters.beamline_parameters import get_beamline_parameters


class AttenuationOptimisationFailedException(Exception):
    pass


class Direction(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class PlaceholderParams:
    """placeholder for the actual params needed for this function"""

    # Gets parameters from GDA i03-config/scripts/beamlineParameters
    @classmethod
    def from_beamline_params(cls, params):
        return (
            params["attenuation_optimisation_type"],  # optimisation type: deadtime
            int(params["fluorescence_attenuation_low_roi"]),  # low_roi: 100
            int(params["fluorescence_attenuation_high_roi"]),  # high_roi: 2048
            params["attenuation_optimisation_start_transmission"]
            / 100,  # initial transmission, /100 to get decimal from percentage: 0.1
            params["attenuation_optimisation_target_count"] * 10,  # target:2000
            params["attenuation_optimisation_lower_limit"],  # lower limit: 20000
            params["attenuation_optimisation_upper_limit"],  # upper limit: 50000
            int(
                params["attenuation_optimisation_optimisation_cycles"]
            ),  # max cycles: 10
            params["attenuation_optimisation_multiplier"],  # increment: 2
            params[
                "fluorescence_analyser_deadtimeThreshold"
            ],  # Threshold for edge scans: 0.002
        )


def create_devices():
    i03.zebra()
    i03.xspress3mini()
    i03.attenuator()


def check_parameters(
    target, upper_limit, lower_limit, default_high_roi, default_low_roi
):
    if target < lower_limit or target > upper_limit:
        raise (
            ValueError(
                f"Target {target} is outside of lower and upper bounds: {lower_limit} to {upper_limit}"
            )
        )

    if default_high_roi < default_low_roi:
        raise ValueError(
            f"Upper roi {default_high_roi} must be greater than lower roi {default_low_roi}"
        )


def is_counts_within_target(total_count, lower_limit, upper_limit) -> bool:
    if lower_limit <= total_count and total_count <= upper_limit:
        return True
    else:
        return False


def arm_devices(xspress3mini, zebra):
    # Arm xspress3mini and zebra
    yield from bps.abs_set(xspress3mini.do_arm, 1, group="xsarm")
    LOGGER.info("Arming Zebra")
    LOGGER.debug("Resetting Zebra")
    yield from bps.abs_set(zebra.pc.reset, 1, group="reset_zebra")
    yield from bps.wait(group="xsarm")
    LOGGER.info("Arming Xspress3Mini complete")
    yield from arm_zebra(zebra)


def deadtime_is_transmission_optimised(
    direction: Direction, deadtime, deadtime_threshold, transmission
) -> tuple[bool, bool]:
    """Compares the deadtime to the deadtime_threshold and determines behavior for the next optimisation iteration

    If deadtime is lower than the threshold or greater than 0.9, returns (True, flip_direction).
    Marks the flip direction as positive if the deadtime has gone over the threshold. Raises error AttenuationOptimisationFailedException if
    transmission goes too low

    Args:
        direction: Enum
        Enum taking values of either POSITIVE or NEGATIVE, which determines whether the transmission should be increased or decreased in the next iteration

        deadtime:
        Current deadtime value

    Returns:
        boolean: marking whether or not attenuation is optimised

        flip_direction: Boolean
        Set to true if the deadtime goes above its threshold while direction is positive. This makes deadtime decrease on the next iteration. Otherwise
        set to false.
    """

    flip_direction = False
    if direction.value == Direction.POSITIVE:
        if deadtime >= deadtime_threshold:
            flip_direction = True
            return False, flip_direction
        else:
            # The 0.9 is hardcoded in GDA
            if transmission >= 0.9:
                return True, flip_direction
    else:
        if deadtime <= deadtime_threshold:
            return True, flip_direction
    return False, flip_direction


def deadtime_calc_new_transmission(direction: Direction, transmission, increment):
    if direction.value == Direction.POSITIVE:
        transmission *= increment
        if transmission > 0.999:
            transmission = 1
    else:
        transmission /= increment
    if transmission < 1.0e-6:
        raise AttenuationOptimisationFailedException(
            "Calculated transmission is below expected limit"
        )
    return transmission


def do_device_optimise_iteration(
    attenuator: Attenuator, zebra: Zebra, xspress3mini: Xspress3Mini, transmission
):
    """Set transmission, set number of images on xspress3mini, arm xspress3mini and zebra"""
    yield from bps.abs_set(attenuator, transmission, group="set_transmission")
    yield from bps.abs_set(xspress3mini.set_num_images, 1, wait=True)
    yield from arm_devices(xspress3mini, zebra)


def deadtime_optimisation(
    attenuator, xspress3mini, zebra, transmission, increment, deadtime_threshold
):
    direction = Direction.POSITIVE
    LOGGER.info(f"Target deadtime is {deadtime_threshold}")

    while True:
        yield from do_device_optimise_iteration(
            attenuator, zebra, xspress3mini, transmission
        )

        total_time = xspress3mini.channel_1.total_time.get()
        reset_ticks = xspress3mini.channel_1.reset_ticks.get()

        LOGGER.info(f"Current total time = {total_time}")
        LOGGER.info(f"Current reset ticks = {reset_ticks}")
        deadtime = 0

        """ Deadtime is the time after each event during which the detector cannot record another event.
            The reset ticks PV gives the (absolute) time at which the last event was processed, so the difference between the total time and the 
            reset ticks time gives the deadtime. Then divide by total time to get it as a percentage.
            
            This percentage can then be used to calculate the real counts. Eg Real counts = observed counts / (deadtime fraction)
        
        """

        if total_time != reset_ticks:
            deadtime = 1 - abs(total_time - reset_ticks) / (total_time)

        LOGGER.info(f"Deadtime is now at {deadtime}")

        is_optimised, flip_direction = deadtime_is_transmission_optimised(
            direction, deadtime, deadtime_threshold, transmission
        )

        if is_optimised:
            optimised_transmission = transmission
            break

        if flip_direction:
            direction = Direction.NEGATIVE

        transmission = deadtime_calc_new_transmission(
            direction, transmission, increment
        )

    return optimised_transmission


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

        yield from do_device_optimise_iteration(
            attenuator, zebra, xspress3mini, transmission
        )

        data = np.array((yield from bps.rd(xspress3mini.dt_corrected_latest_mca)))
        total_count = sum(data[int(low_roi) : int(high_roi)])
        LOGGER.info(f"Total count is {total_count}")

        if is_counts_within_target(total_count, lower_limit, upper_limit):
            optimised_transmission = transmission
            LOGGER.info(
                f"Total count is within accepted limits: {lower_limit}, {total_count}, {upper_limit}"
            )
            break

        else:
            transmission = (target_count / (total_count)) * transmission

        if cycle == max_cycles - 1:
            raise AttenuationOptimisationFailedException(
                f"Unable to optimise attenuation after maximum cycles.\
                                                            Total count is not within limits: {lower_limit} <= {total_count}\
                                                                <= {upper_limit}"
            )

    return optimised_transmission


def optimise_attenuation_plan(
    collection_time,  # Comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    optimisation_type,
    xspress3mini: Xspress3Mini,
    zebra: Zebra,
    attenuator: Attenuator,
    low_roi=None,
    high_roi=None,
):
    (
        _,  # This is optimisation type. Beter for testing if this is a parameter of the plan instead
        default_low_roi,
        default_high_roi,
        initial_transmission,
        target,
        lower_limit,
        upper_limit,
        max_cycles,
        increment,
        deadtime_threshold,
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    check_parameters(
        target, upper_limit, lower_limit, default_high_roi, default_low_roi
    )

    # Hardcode these for now to make more sense
    upper_limit = 4000
    lower_limit = 2000
    target = 3000

    # GDA params currently sets them to 0 by default
    if low_roi is None or low_roi == 0:
        low_roi = default_low_roi
    if high_roi is None or high_roi == 0:
        high_roi = default_high_roi

    yield from bps.abs_set(
        xspress3mini.acquire_time, collection_time, wait=True
    )  # Don't necessarily need to wait here

    # Do the attenuation optimisation using count threshold
    if optimisation_type == "total_counts":
        LOGGER.info(
            f"Starting Xspress3Mini total counts optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )

        optimised_transmission = yield from total_counts_optimisation(
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

    elif optimisation_type == "deadtime":
        LOGGER.info(
            f"Starting Xspress3Mini deadtime optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )
        optimised_transmission = yield from deadtime_optimisation(
            attenuator,
            xspress3mini,
            zebra,
            initial_transmission,
            increment,
            deadtime_threshold,
        )

    yield from bps.abs_set(attenuator, optimised_transmission, group="set_transmission")

    return optimised_transmission
