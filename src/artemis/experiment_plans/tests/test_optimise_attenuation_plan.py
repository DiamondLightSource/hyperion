from unittest.mock import MagicMock

import numpy as np
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.xspress3_mini.xspress3_mini import DetectorState
from ophyd.status import Status

from artemis.experiment_plans.optimise_attenuation_plan import (
    PlaceholderParams,
    optimise_attenuation_plan,
)
from artemis.parameters.beamline_parameters import get_beamline_parameters


def fake_create_devices():
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


def test_optimise(RE: RunEngine):
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
    ) = PlaceholderParams.from_beamline_params(get_beamline_parameters())

    target = 20000

    # Make list so we can modify within function (is there a better way to do this?)
    transmission_list = [transmission]

    # Mock a calculation where the dt_corrected_latest_mca array data
    # is randomly created based on the transmission value
    def mock_set_transmission(_):
        data = np.ones(shape=2048) * (transmission_list[0] + 1)
        total_count = sum(data[int(default_low_roi) : int(default_high_roi)])
        transmission_list[0] = (target / (total_count)) * transmission_list[0]
        xspress3mini.dt_corrected_latest_mca.sim_put(data)
        return get_good_status()

    # attenuator.change.set = MagicMock(side_effect=mock_apply_attenuator_values)
    attenuator.desired_transmission.set = mock_set_transmission

    # Force xspress3mini to pass arming
    xspress3mini.detector_state.sim_put(DetectorState.ACQUIRE.value)

    # Get arming Zebra to work
    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm_demand.set = mock_arm_disarm

    RE(optimise_attenuation_plan(5, 1, xspress3mini, zebra, attenuator, 0, 0))
