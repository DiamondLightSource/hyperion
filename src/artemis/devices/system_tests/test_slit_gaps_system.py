import pytest

from artemis.devices.slit_gaps import SlitGaps


@pytest.mark.s03
def test_when_slit_gaps_created_against_s03_then_can_connect():
    slit_gaps = SlitGaps("BL03S-AL-SLITS-04:", name="slit_gaps")

    slit_gaps.wait_for_connection()
