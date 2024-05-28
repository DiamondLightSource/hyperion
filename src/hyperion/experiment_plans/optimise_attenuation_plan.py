import dataclasses
from enum import Enum

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from blueapi.core import BlueskyContext
from dodal.devices.attenuator import Attenuator
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini
from dodal.devices.zebra_controlled_shutter import ZebraShutter, ZebraShutterState

from hyperion.log import LOGGER
from hyperion.utils.context import device_composite_from_context


class AttenuationOptimisationFailedException(Exception):
    pass


class Direction(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclasses.dataclass
class OptimizeAttenuationComposite:
    """All devices which are directly or indirectly required by this plan"""

    attenuator: Attenuator
    sample_shutter: ZebraShutter
    xspress3mini: Xspress3Mini


def create_devices(context: BlueskyContext) -> OptimizeAttenuationComposite:
    return device_composite_from_context(context, OptimizeAttenuationComposite)


def check_parameters(
    target,
    upper_count_limit,
    lower_count_limit,
    default_high_roi,
    default_low_roi,
    initial_transmission,
    upper_transmission,
    lower_transmission,
):
    if target < lower_count_limit or target > upper_count_limit:
        raise (
            ValueError(
                f"Target {target} is outside of lower and upper bounds: {lower_count_limit} to {upper_count_limit}"
            )
        )

    if default_high_roi < default_low_roi:
        raise ValueError(
            f"Upper roi {default_high_roi} must be greater than lower roi {default_low_roi}"
        )

    if upper_transmission < lower_transmission:
        raise ValueError(
            f"Upper transmission limit {upper_transmission} must be greater than lower tranmission limit {lower_transmission}"
        )

    if not upper_transmission >= initial_transmission >= lower_transmission:
        raise ValueError(
            f"initial transmission {initial_transmission} is outside range {lower_transmission} - {upper_transmission}"
        )


def is_counts_within_target(total_count, lower_count_limit, upper_count_limit) -> bool:
    if lower_count_limit <= total_count and total_count <= upper_count_limit:
        return True
    else:
        return False


def arm_devices(xspress3mini: Xspress3Mini):
    yield from bps.abs_set(xspress3mini.do_arm, 1, wait=True)
    LOGGER.info("Arming Xspress3Mini complete")


def calculate_new_direction(direction: Direction, deadtime, deadtime_threshold):
    if direction == Direction.POSITIVE:
        if deadtime > deadtime_threshold:
            direction = Direction.NEGATIVE
            LOGGER.info(
                "Found tranmission to go above deadtime threshold. Reducing transmission..."
            )
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
    composite: OptimizeAttenuationComposite,
    transmission,
):
    def close_shutter():
        yield from bps.abs_set(
            composite.sample_shutter, ZebraShutterState.CLOSE, wait=True
        )

    @bpp.finalize_decorator(close_shutter)
    def open_and_run():
        """Set transmission, set number of images on xspress3mini, arm xspress3mini"""
        yield from bps.abs_set(
            composite.attenuator, transmission, group="set_transmission"
        )
        yield from bps.abs_set(composite.xspress3mini.set_num_images, 1, wait=True)
        yield from bps.abs_set(
            composite.sample_shutter, ZebraShutterState.OPEN, wait=True
        )
        yield from bps.abs_set(composite.xspress3mini.do_arm, 1, wait=True)

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
    composite: OptimizeAttenuationComposite,
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

    This algorithm gradually increases the transmission until the percentage deadtime goes beneath the specified threshold. It then increases
    the transmission and stops when the deadtime goes above the threshold. A smaller increment will provide a better optimised value, but take more
    cycles to complete.

    Args:
        attenuator: (Attenuator) Ophyd device

        xspress3mini: (Xspress3Mini) Ophyd device

        sample_shutter: (SampleShutter) Ophyd_async device for the fast shutter

        transmission: (float)
        The initial transmission value to use for the optimising

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
        yield from do_device_optimise_iteration(composite, transmission)

        total_time = float(composite.xspress3mini.channel_1.total_time.get())
        reset_ticks = float(composite.xspress3mini.channel_1.reset_ticks.get())

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
    composite: OptimizeAttenuationComposite,
    transmission: float,
    low_roi: int,
    high_roi: int,
    lower_count_limit: float,
    upper_count_limit: float,
    target_count: float,
    max_cycles: int,
    upper_transmission_limit: float,
    lower_transmission_limit: float,
):
    """Optimises the attenuation for the Xspress3Mini based on the total counts

    This loop adjusts the transmission of the attenuator and checks the total counts of the detector until the total counts as in the acceptable range,
    defined by the lower and upper limit. To protect the sample, the transmission has a maximum value of 10%.

    Args:
        attenuator: (Attenuator) Ophyd device

        xspress3mini: (Xspress3Mini) Ophyd device

        sample_shutter: (SampleShutter) Ophyd_async device for the fast shutter

        transmission: (float)
        The initial transmission value to use for the optimising

        low_roi: (float)
        Lower region of interest at which to include in the counts

        high_roi: (float)
        Upper region of interest at which to include in the counts

        lower_count_limit: (float)
        The lowest acceptable value for count

        upper_count_limit: (float)
        The highest acceptable value for count

        target_count: (int)
        The ideal number of target counts - used to calculate the transmission for the subsequent iteration.

        max_cycles: (int)
        The maximum number of iterations before an error is thrown

        upper_transmission_limit: (float)
        The maximum allowed value for the transmission

        lower_transmission_limit: (float)
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

        yield from do_device_optimise_iteration(composite, transmission)

        data = np.array(
            (yield from bps.rd(composite.xspress3mini.dt_corrected_latest_mca))
        )
        total_count = sum(data[int(low_roi) : int(high_roi)])
        LOGGER.info(f"Total count is {total_count}")

        if is_counts_within_target(total_count, lower_count_limit, upper_count_limit):
            optimised_transmission = transmission
            LOGGER.info(
                f"Total count is within accepted limits: {lower_count_limit}, {total_count}, {upper_count_limit}"
            )
            break
        elif transmission == upper_transmission_limit:
            LOGGER.warning(
                f"Total count is not within limits: {lower_count_limit} <= {total_count} <= {upper_count_limit}\
                    after using maximum transmission {upper_transmission_limit}. Continuing\
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
                                                            Total count is not within limits: {lower_count_limit} <= {total_count}\
                                                                <= {upper_count_limit}"
            )

    return optimised_transmission


def optimise_attenuation_plan(
    composite: OptimizeAttenuationComposite,
    collection_time=1,  # Comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    optimisation_type="deadtime",
    low_roi=100,
    high_roi=2048,
    upper_transmission_limit=0.1,
    lower_transmission_limit=1.0e-6,
    initial_transmission=0.1,
    target_count=20000,
    lower_count_limit=20000,
    upper_count_limit=50000,
    max_cycles=10,
    increment=2,
    deadtime_threshold=0.002,
):
    check_parameters(
        target_count,
        upper_count_limit,
        lower_count_limit,
        high_roi,
        low_roi,
        initial_transmission,
        upper_transmission_limit,
        lower_transmission_limit,
    )

    yield from bps.abs_set(
        composite.xspress3mini.acquire_time, collection_time, wait=True
    )  # Don't necessarily need to wait here

    # Do the attenuation optimisation using count threshold
    if optimisation_type == "total_counts":
        LOGGER.info(
            f"Starting Xspress3Mini total counts optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )

        optimised_transmission = yield from total_counts_optimisation(
            composite,
            initial_transmission,
            low_roi,
            high_roi,
            lower_count_limit,
            upper_count_limit,
            target_count,
            max_cycles,
            upper_transmission_limit,
            lower_transmission_limit,
        )

    elif optimisation_type == "deadtime":
        LOGGER.info(
            f"Starting Xspress3Mini deadtime optimisation routine \nOptimisation will be performed across ROI channels {low_roi} - {high_roi}"
        )
        optimised_transmission = yield from deadtime_optimisation(
            composite,
            initial_transmission,
            upper_transmission_limit,
            lower_transmission_limit,
            increment,
            deadtime_threshold,
            max_cycles,
        )

    yield from bps.abs_set(
        composite.attenuator,
        optimised_transmission,
        group="set_transmission",
        wait=True,
    )

    return optimised_transmission
