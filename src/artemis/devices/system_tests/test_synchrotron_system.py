import pytest

from artemis.devices.synchrotron import Synchrotron


@pytest.fixture
def synchrotron():
    synchrotron = Synchrotron("", name="synchrotron")
    return synchrotron


@pytest.mark.s03
def test_synchrotron_connects(synchrotron: Synchrotron):
    synchrotron.wait_for_connection()
