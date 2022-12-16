import pytest

from artemis.devices.I03Smargon import I03Smargon


@pytest.mark.s03
def test_when_smargon_created_against_s03_then_can_connect():
    smargon = I03Smargon("BL03S", name="smargon")

    smargon.wait_for_connection()
