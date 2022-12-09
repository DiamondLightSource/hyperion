import pytest

from artemis.devices.synchrotron import Synchrotron
from artemis.parameters.constants import SIM_BEAMLINE


@pytest.fixture
def synchrotron():
    synchrotron = Synchrotron(f"{SIM_BEAMLINE}-", name="synchrotron")
    return synchrotron


@pytest.mark.s03
def test_synchrotron_connects(synchrotron: Synchrotron):
    synchrotron.wait_for_connection()
