import pytest

from artemis.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from artemis.parameters import I03_BEAMLINE_PARAMETER_PATH, GDABeamlineParameters


@pytest.fixture
def ap_sc():
    ap_sc = ApertureScatterguard(prefix="BL03S", name="aperture")
    return ap_sc


@pytest.mark.s03
def test_can_connect_s03_apsc(ap_sc: ApertureScatterguard):
    ap_sc.wait_for_connection()


@pytest.mark.s03
def test_ap_sc_can_load_positions_from_beamline_params(ap_sc: ApertureScatterguard):
    ap_sc.load_aperture_positions(
        AperturePositions.from_gda_beamline_params(
            GDABeamlineParameters.from_file(I03_BEAMLINE_PARAMETER_PATH)
        )
    )
    assert ap_sc.aperture_positions is not None
