import pytest

from src.artemis.devices.undulator import Undulator
from src.artemis.parameters import SIM_INSERTION_PREFIX


@pytest.fixture
def undulator():
    undulator = Undulator(f"{SIM_INSERTION_PREFIX}-MO-SERVC-01:", name="undulator")
    return undulator


@pytest.mark.s03
def test_undulator_connects(undulator):
    undulator.wait_for_connection()
