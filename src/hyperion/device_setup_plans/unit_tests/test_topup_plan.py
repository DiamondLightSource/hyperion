from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.synchrotron import SynchrotronMode

from hyperion.device_setup_plans.check_topup import check_topup_and_wait_if_necessary
from hyperion.parameters import external_parameters
from hyperion.parameters.internal_parameters import HyperionParameters


@pytest.fixture
def synchrotron():
    return i03.synchrotron(fake_with_ophyd_sim=True)


@pytest.fixture
def fake_parameters():
    params = external_parameters.from_file(
        "src/hyperion/parameters/tests/test_data/hyperion_parameters.json"
    )
    parameters = HyperionParameters(**params)
    return parameters.detector_params


@patch("src.hyperion.device_setup_plans.check_topup.bps.sleep")
def test_when_topup_before_end_of_collection_wait(
    fake_sleep, fake_parameters, synchrotron
):
    synchrotron.top_up.start_countdown.sim_put(20.0)
    synchrotron.top_up.end_countdown.sim_put(60.0)

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            params=fake_parameters,
        )
    )
    fake_sleep.assert_called_once_with(60.0)


@patch("src.hyperion.device_setup_plans.check_topup.bps.null")
def test_no_waiting_if_decay_mode(fake_null, fake_parameters, synchrotron):
    synchrotron.top_up.start_countdown.sim_put(-1)

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            params=fake_parameters,
        )
    )
    fake_null.assert_called_once()


@patch("src.hyperion.device_setup_plans.check_topup.bps.null")
def test_no_waiting_when_mode_does_not_allow_gating(
    fake_null, fake_parameters, synchrotron
):
    synchrotron.machine_status.synchrotron_mode.sim_put(SynchrotronMode.SHUTDOWN)

    RE = RunEngine()
    RE(
        check_topup_and_wait_if_necessary(
            synchrotron=synchrotron,
            params=fake_parameters,
        )
    )
    fake_null.assert_called_once()
