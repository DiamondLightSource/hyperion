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
    collection_time,  # Comes from self.parameters.acquisitionTime in fluorescence_spectrum.py
    params: beamline_parameters,
    xspress3mini: Xspress3Mini,
    zebra: Zebra,
    attenuator: Attenuator,
    low_roi=0,
    high_roi=0,
):
    # Get parameters. Should we get these within the device or plan?

    (
        optimisation_type,
        default_low_roi,
        default_high_roi,
        transmission,
        target,
        lower_limit,
        upper_limit,
        max_cycles,
        increment,
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    # TODO: investigate why default upper limit and lower limit are out from target
    # by a factor of 10. Hardcode these for now
    lower_limit = 2000
    upper_limit = 4000
    target = 3000

    # from_beamline_params reads this as a float
    max_cycles = int(max_cycles)

    write_hdf5_files = False

    # Hardcode this for now:
    optimisation_type = "total_counts"

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

    # Do the attenuation optimisation using count threshold
    if optimisation_type == "total_counts":
        LOGGER.info("Using total count optimisation")

        for cycle in range(0, max_cycles):
            LOGGER.info(
                f"Setting transmission to {transmission} for attenuation optimisation cycle {cycle}"
            )

            yield from bps.abs_set(
                attenuator.do_set_transmission, transmission, group="set_transmission"
            )

            yield from bps.abs_set(xspress3mini.set_num_images, 1, wait=True)
            # TODO: Find out when this variable is true
            if write_hdf5_files:
                yield from bps.abs_set(xspress3mini.hdf_num_capture, 1, wait=False)

            # Arm xspress3mini
            yield from bps.abs_set(xspress3mini.do_arm, 1, group="xsarm")
            yield from bps.wait(group="xsarm")
            LOGGER.info("Arming Xspress3Mini complete")

            LOGGER.info("Arming Zebra")
            LOGGER.debug("Resetting Zebra")
            yield from bps.abs_set(zebra.pc.reset, 1, group="reset_zebra")
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

            transmission = (target / (total_count)) * transmission

            if cycle == max_cycles - 1:
                raise AttenuationOptimisationFailedException(
                    f"Unable to optimise attenuation after maximum cycles.\
                                                             Total count is not within limits: {lower_limit} <= {total_count}\
                                                                  <= {upper_limit}"
                )

        return optimised_transmission
