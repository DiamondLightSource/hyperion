import pytest

from artemis.devices.synchrotron import Synchrotron
from artemis.parameters import SIM_BEAMLINE

SIGNAL = 300
MODE = "Shutdown"
USERCOUNTDN = 100000
BEAMENERGY = 3
COUNTDOWN = 600
ENDCOUNTDN = 610


@pytest.fixture
def synchrotron():
    synchrotron = Synchrotron(f"{SIM_BEAMLINE}-", name="synchrotron")
    return synchrotron


@pytest.mark.s03
def test_synchrotron_connects(synchrotron: Synchrotron):
    synchrotron.wait_for_connection()


@pytest.mark.s03
def test_get_values(synchrotron: Synchrotron):
    assert synchrotron.ring_current.get() == SIGNAL
    assert synchrotron.machine_status.synchrotron_mode.get() == MODE
    assert synchrotron.machine_status.user_countdown.get() == USERCOUNTDN
    assert synchrotron.machine_status.beam_energy.get() == BEAMENERGY
    assert synchrotron.top_up.start_countdown.get() == COUNTDOWN
    assert synchrotron.top_up.end_countdown.get() == ENDCOUNTDN
