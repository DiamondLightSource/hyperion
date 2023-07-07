from enum import Enum

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.sample_shutter import SampleShutter
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini

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
        return ("deadtime", 100, 2048, 0.001, 50, 40, 60, 10, 2, 0.0005)
        # optimisation type, low roi, high roi, start transmission, target count, lower count, upper count, max cycles, deadtime increment,
        # lower deadtime threshold

        # return (
        #     params["attenuation_optimisation_type"],  # optimisation type: deadtime
        #     int(params["fluorescence_attenuation_low_roi"]),  # low_roi: 100
        #     int(params["fluorescence_attenuation_high_roi"]),  # high_roi: 2048
        #     params["attenuation_optimisation_start_transmission"]
        #     / 100,  # initial transmission, /100 to get decimal from percentage: 0.1
        #     params["attenuation_optimisation_target_count"] * 10,  # target:2000
        #     params["attenuation_optimisation_lower_limit"],  # lower limit: 20000
        #     params["attenuation_optimisation_upper_limit"],  # upper limit: 50000
        #     int(
        #         params["attenuation_optimisation_optimisation_cycles"]
        #     ),  # max cycles: 10
        #     params["attenuation_optimisation_multiplier"],  # increment: 2
        #     params[
        #         "fluorescence_analyser_deadtimeThreshold"
        #     ],  # Threshold for edge scans: 0.002
        # )


def create_devices():
    i03.xspress3mini()
    i03.attenuator()
    i03.sample_shutter()


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


def arm_devices(xspress3mini):
    # Arm xspress3mini and TODO: what else does this func do?
    yield from bps.abs_set(xspress3mini.do_arm, 1, wait=True)
    LOGGER.info("Arming Xspress3Mini complete")


def calculate_new_direction(direction: Direction, deadtime, deadtime_threshold):
    if direction == Direction.POSITIVE:
        if deadtime > deadtime_threshold:
            direction = Direction.NEGATIVE
            LOGGER.info("flipping direction")
    return direction


def deadtime_calc_new_transmission(
    direction: Direction,
    transmission: float,
    increment: float,
    upper_transmission_limit: float,
    lower_transmission_limit: float,
) -> float:
    """Calculate the new transmission value based on the current direction and increment. Raise error if transmission is too low.

    Args:
        direction (Direction):
        If positive, increase transmission by a factor of the increment. If negative, divide it

        transmission (float):
        Current transmission value

        increment (float):
        Factor to multiply or divide transmission by

        upper_transmission_limit (float):
        Maximum allowed transmission, in order to protect sample.

        lower_transmission_limit (float):
        Minimum expected transmission. Raise an error if transmission goes lower.

    Raises:
        AttenuationOptimisationFailedException:
        This error is thrown if the transmission goes below the expected value or if the maximum cycles are reached

    Returns:
        transmission (float): Optimised transmission value
    """
    if direction == Direction.POSITIVE:
        transmission *= increment
        if transmission > upper_transmission_limit:
            transmission = upper_transmission_limit
    else:
        transmission /= increment
    if transmission < lower_transmission_limit:
        raise AttenuationOptimisationFailedException(
            "Calculated transmission is below expected limit"
        )
    return transmission


def do_device_optimise_iteration(
    attenuator: Attenuator,
    xspress3mini: Xspress3Mini,
    sample_shutter: SampleShutter,
    transmission,
):
    def close_shutter():
        yield from bps.abs_set(sample_shutter, sample_shutter.CLOSE, wait=True)

    @bpp.finalize_decorator(close_shutter)
    def open_and_run():
        """Set transmission, set number of images on xspress3mini, arm xspress3mini"""
        yield from bps.abs_set(attenuator, transmission, group="set_transmission")
        yield from bps.abs_set(xspress3mini.set_num_images, 1, wait=True)
        yield from bps.abs_set(sample_shutter, sample_shutter.OPEN, wait=True)
        yield from bps.abs_set(xspress3mini.do_arm, 1, wait=True)

    yield from open_and_run()


def is_deadtime_optimised(
    deadtime: float,
    deadtime_threshold: float,
    transmission: float,
    upper_transmission_limit: float,
    direction: Direction,
) -> bool:
    if direction == Direction.POSITIVE:
        if transmission == upper_transmission_limit:
            if transmission == upper_transmission_limit:
                LOGGER.warning(
                    f"Deadtime {deadtime} is above threshold {deadtime_threshold} at maximum transmission {upper_transmission_limit}. Using maximum transmission\
                            as optimised value."
                )
            return True
    # Once direction is flipped and deadtime goes back above threshold, we consider attenuation to be optimised.
    else:
        if deadtime <= deadtime_threshold:
            return True
    return False


def deadtime_optimisation(
    attenuator: Attenuator,
    xspress3mini: Xspress3Mini,
    sample_shutter: SampleShutter,
    transmission: float,
    increment: float,
    deadtime_threshold: float,
    max_cycles: int,
    upper_transmission_limit: float,
    lower_transmission_limit: float,
):
    """Optimises the attenuation for the Xspress3Mini based on the detector deadtime

    Deadtime is the time after each event during which the detector cannot record another event. This loop adjusts the transmission of the attenuator
    and checks the deadtime until the percentage deadtime is below the accepted threshold. To protect the sample, the transmission has a maximum value

    Here we use the percentage deadtime - the percentage of time to which the detector is unable to process events.

    This algorithm gradually increases the transmisssion until the percentage deadtime goes beneath the specified threshold. It then increases
    the transmission and stops when the deadtime goes above the threshold. A smaller increment will provide a better optimised value, but take more
    cycles to complete.

    Args:
        attenuator: (Attenuator) Ophyd device

        xspress3mini: (Xspress3Mini) Ophyd device

        sample_shutter: (SampleShutter) Ophyd device for the fast shutter

        transmission: (float)
        The intial transmission value to use for the optimising

        increment: (float)
        The factor to increase / decrease the transmission by each iteration

        deadtime_threshold: (float)
        The maximum acceptable percentage deadtime

        max_cycles: (int)
        The maximum number of iterations before an error is thrown

        upper_transmission_limit (float):
        Maximum allowed transmission, in order to protect sample.

        lower_transmission_limit (float):
        Minimum expected transmission. Raise an error if transmission goes lower.

    Raises:
        AttenuationOptimisationFailedException:
        This error is thrown if the transmission goes below the expected value or the maximum cycles are reached

    Returns:
        optimised_transmission: (float)
        The final transmission value which produces an acceptable deadtime
    """

    direction = Direction.POSITIVE
    LOGGER.info(f"Target deadtime is {deadtime_threshold}")

    for cycle in range(0, max_cycles):
        yield from do_device_optimise_iteration(
            attenuator, xspress3mini, sample_shutter, transmission
        )

        total_time = xspress3mini.channel_1.total_time.get()
        reset_ticks = xspress3mini.channel_1.reset_ticks.get()

        LOGGER.info(f"Current total time = {total_time}")
        LOGGER.info(f"Current reset ticks = {reset_ticks}")
        deadtime = 0

        """ 
            The reset ticks PV stops ticking while the detector is unable to process events, so the absolute difference between the total time and the
            reset ticks time gives the deadtime in unit time. Divide by total time to get it as a percentage.
        """

        if total_time != reset_ticks:
            deadtime = 1 - abs(total_time - reset_ticks) / (total_time)

        LOGGER.info(f"Deadtime is now at {deadtime}")

        # Check if new deadtime is OK

        if is_deadtime_optimised(
            deadtime,
            deadtime_threshold,
            transmission,
            upper_transmission_limit,
            direction,
        ):
            optimised_transmission = transmission
            break

        if cycle == max_cycles - 1:
            raise AttenuationOptimisationFailedException(
                f"Unable to optimise attenuation after maximum cycles.\
                                                            Deadtime did not get lower than threshold: {deadtime_threshold} in maximum cycles {max_cycles}"
            )

        direction = calculate_new_direction(direction, deadtime, deadtime_threshold)

        transmission = deadtime_calc_new_transmission(
            direction,
            transmission,
            increment,
            upper_transmission_limit,
            lower_transmission_limit,
        )

    return optimised_transmission


def total_counts_optimisation(
    attenuator: Attenuator,
    xspress3mini: Xspress3Mini,
    sample_shutter: SampleShutter,
    transmission: float,
    low_roi: int,
    high_roi: int,
    lower_limit: float,
    upper_limit: float,
    target_count: float,
    max_cycles: int,
    upper_transmission_limit: int,
    lower_transmission_limit: int,
):
    """Optimises the attenuation for the Xspress3Mini based on the total counts

    This loop adjusts the transmission of the attenuator and checks the total counts of the detector until the total counts as in the acceptable range,
    defined by the lower and upper limit. To protect the sample, the transmission has a maximum value of 10%.

    Args:
        attenuator: (Attenuator) Ophyd device

        xspress3mini: (Xspress3Mini) Ophyd device

        sample_shutter: (SampleShutter) Ophyd device for the fast shutter

        transmission: (float)
        The intial transmission value to use for the optimising

        low_roi: (float)
        Lower region of interest at which to include in the counts

        high_roi: (float)
        Upper region of interest at which to include in the counts

        lower_limit: (float)
        The lowest acceptable value for count

        upper_limit: (float)
        The highest acceptable value for count

        target_count: (int)
        The ideal number of target counts - used to calculate the transmission for the subsequent iteration.

        max_cycles: (int)
        The maximum number of iterations before an error is thrown

        upper_transmission_limit: (int)
        The maximum allowed value for the transmission

        lower_transmission_limit: (int)
        The minimum allowed value for the transmission

    Returns:
        optimised_transmission: (float)
        The final transmission value which produces an acceptable total_count value
    """

    LOGGER.info("Using total count optimisation")

    for cycle in range(0, max_cycles):
        LOGGER.info(
            f"Setting transmission to {transmission} for attenuation optimisation cycle {cycle}"
        )

        yield from do_device_optimise_iteration(
            attenuator, xspress3mini, sample_shutter, transmission
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
        elif transmission == upper_transmission_limit:
            LOGGER.warning(
                f"Total count is not within limits: {lower_limit} <= {total_count}\
                                                                <= {upper_limit} after using maximum transmission {upper_transmission_limit}. Continuing \
                                                                    with maximum transmission as optimised value..."
            )
            optimised_transmission = transmission
            break

        else:
            transmission = (target_count / (total_count)) * transmission
            if transmission > upper_transmission_limit:
                transmission = upper_transmission_limit
            elif transmission < lower_transmission_limit:
                raise AttenuationOptimisationFailedException(
                    f"Transmission has gone below lower threshold {lower_transmission_limit}"
                )

        if cycle == max_cycles - 1:
            raise AttenuationOptimisationFailedException(
                f"Unable to optimise attenuation after maximum cycles.\
                                                            Total count is not within limits: {lower_limit} <= {total_count}\
                                                                <= {upper_limit}"
            )

    return optimised_transmission


# TODO EXTRA TESTS: test shutter, test that warning is thrown if max transmission is reached, test error thrown if transmission goes too low,
# TEST  transmission can never go above limit in either algorithm


# TODO: move all parameters into this first bit and give them all default values except the devices
def optimise_attenuation_plan(
    collection_time,  # Comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    optimisation_type,
    xspress3mini: Xspress3Mini,
    attenuator: Attenuator,
    sample_shutter: SampleShutter,
    low_roi=None,
    high_roi=None,
    upper_transmission_limit=0.9,
    lower_transmission_limit=1.0e-6,
):
    (
        _,  # This is optimisation type. While we can get it from GDA, it's better for testing if this is a parameter of the plan instead
        default_low_roi,
        default_high_roi,
        initial_transmission,
        target,
        lower_limit,
        upper_limit,
        max_cycles,
        increment,
        deadtime_threshold,
    ) = PlaceholderParams.from_beamline_params(
        get_beamline_parameters()
    )  # TODO: move all of these parameters into otimise_attenuation_plan  - dont use GDA for params at all

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
            attenuator,
            xspress3mini,
            sample_shutter,
            initial_transmission,
            low_roi,
            high_roi,
            lower_limit,
            upper_limit,
            target,
            max_cycles,
            upper_transmission_limit,
            lower_transmission_limit,
        )

    elif optimisation_type == "deadtime":
        LOGGER.info(
            f"Starting Xspress3Mini deadtime optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )
        optimised_transmission = yield from deadtime_optimisation(
            attenuator,
            xspress3mini,
            sample_shutter,
            initial_transmission,
            upper_transmission_limit,
            lower_transmission_limit,
            increment,
            deadtime_threshold,
            max_cycles,
        )

    yield from bps.abs_set(
        attenuator, optimised_transmission, group="set_transmission", wait=True
    )

    return optimised_transmission
