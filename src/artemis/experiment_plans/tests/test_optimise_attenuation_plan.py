from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.xspress3_mini.xspress3_mini import DetectorState, Xspress3Mini
from dodal.devices.zebra import Zebra
from ophyd.status import Status

from artemis.experiment_plans import optimise_attenuation_plan
from artemis.experiment_plans.optimise_attenuation_plan import (
    AttenuationOptimisationFailedException,
    Direction,
    PlaceholderParams,
    arm_devices,
    check_parameters,
    create_devices,
    deadtime_calc_new_transmission,
    deadtime_is_transmission_optimised,
    is_counts_within_target,
    total_counts_optimisation,
)
from artemis.parameters.beamline_parameters import get_beamline_parameters


def fake_create_devices() -> tuple[Zebra, Xspress3Mini, Attenuator]:
    zebra = i03.zebra(fake_with_ophyd_sim=True)
    zebra.wait_for_connection()
    xspress3mini = i03.xspress3mini(fake_with_ophyd_sim=True)
    xspress3mini.wait_for_connection()
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    attenuator.wait_for_connection()
    return zebra, xspress3mini, attenuator


"""Default params:
default_low_roi = 100
default_high_roi = 2048
increment = 2
lower_lim = 20000
upper_lim = 50000
transmission = 0.1

Produce an array with 1000 values between 0-1 * (1+transmission)
"""
CALCULATED_VALUE = 0


def get_good_status():
    status = Status()
    status.set_finished()
    return status


@patch("artemis.experiment_plans.optimise_attenuation_plan.arm_zebra")
def test_total_count_optimise(mock_arm_zebra, RE: RunEngine):
    """Test the overall total count algorithm"""
    zebra, xspress3mini, attenuator = fake_create_devices()

    # Mimic some of the logic to track the transmission and set realistic data
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
        deadtime_threshold,
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    # Same as plan target
    target = 3000

    # Make list so we can modify within function (is there a better way to do this?)
    transmission_list = [transmission]

    # Mock a calculation where the dt_corrected_latest_mca array data
    # is created based on the transmission value
    def mock_set_transmission(_):
        data = np.ones(shape=2048) * (transmission_list[0] + 1)
        total_count = sum(data[int(default_low_roi) : int(default_high_roi)])
        transmission_list[0] = (target / (total_count)) * transmission_list[0]
        xspress3mini.dt_corrected_latest_mca.sim_put(data)
        return get_good_status()

    attenuator.desired_transmission.set = mock_set_transmission

    # Force xspress3mini to pass arming
    xspress3mini.detector_state.sim_put(DetectorState.ACQUIRE.value)

    RE(
        optimise_attenuation_plan.optimise_attenuation_plan(
            5, "total_counts", xspress3mini, zebra, attenuator, 0, 0
        )
    )


@pytest.mark.parametrize(
    "high_roi, low_roi",
    [(0, 0), (0, 2048)],
)
@patch("artemis.experiment_plans.optimise_attenuation_plan.arm_zebra")
def test_deadtime_optimise(mock_arm_zebra, high_roi, low_roi, RE: RunEngine):
    """Test the overall deadtime optimisation"""

    zebra, xspress3mini, attenuator = fake_create_devices()

    # Mimic some of the logic to track the transmission and set realistic data
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
        deadtime_threshold,
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    """ Similar to test_total_count, mimic the set transmission. For now, just assume total time is constant and increasing the transmission will increase the
    reset ticks, thus decreasing the deadtime"""
    transmission_list = [transmission]
    direction_list = [True]
    total_time = 8e7

    # Put realistic values into PV's
    xspress3mini.channel_1.total_time.sim_put(8e7)
    xspress3mini.channel_1.reset_ticks.sim_put(151276)

    def mock_set_transmission(_):
        # Update reset ticks, calc new deadtime, increment transmission.
        reset_ticks = 151276 * transmission_list[0]
        deadtime = 0
        if total_time != reset_ticks:
            deadtime = 1 - abs(float(total_time - reset_ticks)) / float(total_time)

        _, direction_flip = deadtime_is_transmission_optimised(
            direction_list[0], deadtime, deadtime_threshold, transmission
        )
        if direction_flip:
            direction_list[0] = not direction_list[0]

        if direction_list[0]:
            transmission_list[0] *= increment
        else:
            transmission_list[0] /= increment

        return get_good_status()

    attenuator.desired_transmission.set = mock_set_transmission
    # Force xspress3mini to pass arming
    xspress3mini.detector_state.sim_put(DetectorState.ACQUIRE.value)
    RE(
        optimise_attenuation_plan.optimise_attenuation_plan(
            5, "deadtime", xspress3mini, zebra, attenuator, high_roi, low_roi
        )
    )


@pytest.mark.parametrize(
    "target, upper_limit, lower_limit, default_high_roi, default_low_roi",
    [(100, 90, 110, 1, 0), (50, 100, 20, 10, 20), (100, 100, 101, 10, 1)],
)
def test_check_parameters_fail_on_out_of_range_parameters(
    target, upper_limit, lower_limit, default_high_roi, default_low_roi
):
    with pytest.raises(ValueError):
        check_parameters(
            target, upper_limit, lower_limit, default_high_roi, default_low_roi
        )


def test_check_parameters_runs_on_correct_params():
    assert check_parameters(10, 100, 0, 2, 1) is None


@pytest.mark.parametrize(
    "total_count, lower_limit, upper_limit",
    [(100, 99, 100), (100, 100, 100), (50, 25, 1000)],
)
def test_is_counts_within_target_is_true(total_count, lower_limit, upper_limit):
    assert is_counts_within_target(total_count, lower_limit, upper_limit) is True


@pytest.mark.parametrize(
    "total_count, lower_limit, upper_limit",
    [(100, 101, 101), (0, 1, 2), (1000, 2000, 3000)],
)
def test_is_counts_within_target_is_false(total_count, lower_limit, upper_limit):
    assert is_counts_within_target(total_count, lower_limit, upper_limit) is False


def test_total_count_exception_raised_after_max_cycles_reached(RE: RunEngine):
    zebra, xspress3mini, attenuator = fake_create_devices()
    optimise_attenuation_plan.is_counts_within_target = MagicMock(return_value=False)
    optimise_attenuation_plan.arm_zebra = MagicMock()
    xspress3mini.arm = MagicMock(return_value=get_good_status())
    xspress3mini.dt_corrected_latest_mca.sim_put([1, 1, 1, 1, 1, 1])
    with pytest.raises(AttenuationOptimisationFailedException):
        RE(
            total_counts_optimisation(
                attenuator, xspress3mini, zebra, 1, 0, 1, 0, 1, 5, 10
            )
        )


def test_arm_devices_runs_correct_functions(RE: RunEngine):
    zebra, xspress3mini, _ = fake_create_devices()
    xspress3mini.detector_state.sim_put("Acquire")
    optimise_attenuation_plan.arm_zebra = MagicMock()
    xspress3mini.arm = MagicMock(return_value=get_good_status())
    RE(arm_devices(xspress3mini, zebra))
    xspress3mini.arm.assert_called_once()
    optimise_attenuation_plan.arm_zebra.assert_called_once()


@pytest.mark.parametrize(
    "direction, transmission, increment, upper_limit, lower_limit, new_transmission",
    [
        (Direction.POSITIVE, 0.5, 2, 0.9, 1e-6, 0.9),
        (Direction.POSITIVE, 0.1, 2, 0.9, 1e-6, 0.2),
        (Direction.NEGATIVE, 0.8, 2, 0.9, 1e-6, 0.4),
    ],
)
def test_deadtime_calc_new_transmission_gets_correct_value(
    direction, transmission, increment, upper_limit, lower_limit, new_transmission
):
    assert (
        deadtime_calc_new_transmission(
            direction, transmission, increment, upper_limit, lower_limit
        )
        == new_transmission
    )


def test_deadtime_calc_new_transmission_raises_error_on_low_ransmission():
    with pytest.raises(AttenuationOptimisationFailedException):
        deadtime_calc_new_transmission(Direction.NEGATIVE, 1e-6, 2, 1, 1e-6)


def test_create_new_devices():
    with patch("artemis.experiment_plans.optimise_attenuation_plan.i03") as i03:
        create_devices()
        i03.zebra.assert_called()
        i03.xspress3mini.assert_called()
        i03.attenuator.assert_called()
