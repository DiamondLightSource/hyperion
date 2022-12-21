import pytest

from artemis.devices.s4_slits import S4Slits


@pytest.mark.s03
def test_when_s4_slits_created_against_s03_then_can_connect():
    slit_gaps = S4Slits("BL03S-AL-SLITS-04:", name="s4slits")

    slit_gaps.wait_for_connection()
