import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine

from artemis.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from artemis.parameters import I03_BEAMLINE_PARAMETER_PATH, GDABeamlineParameters


@pytest.fixture
def ap_sc():
    ap_sc = ApertureScatterguard(prefix="BL03S", name="aperture")
    ap_sc.load_aperture_positions(
        AperturePositions.from_gda_beamline_params(
            GDABeamlineParameters.from_file(I03_BEAMLINE_PARAMETER_PATH)
        )
    )
    return ap_sc


@pytest.mark.s03
def test_aperturescatterguard_setup(ap_sc: ApertureScatterguard):
    ap_sc.wait_for_connection()
    assert ap_sc.aperture_positions is not None


@pytest.mark.s03
def test_aperturescatterguard_move_in_plan(ap_sc: ApertureScatterguard):
    RE = RunEngine({})
    ap_sc.wait_for_connection()

    ap_sc.aperture.z.set(ap_sc.aperture_positions.LARGE[2], wait=True)

    def move_to_large():
        yield from bps.abs_set(ap_sc, ap_sc.aperture_positions.LARGE)

    def move_to_medium():
        yield from bps.abs_set(ap_sc, ap_sc.aperture_positions.MEDIUM)

    def move_to_small():
        yield from bps.abs_set(ap_sc, ap_sc.aperture_positions.SMALL)

    def move_to_robotload():
        yield from bps.abs_set(ap_sc, ap_sc.aperture_positions.ROBOT_LOAD)

    RE(move_to_large())
    RE(move_to_medium())
    RE(move_to_small())
    RE(move_to_robotload())


def test_move_fails_when_not_in_good_starting_pos(ap_sc: ApertureScatterguard):
    RE = RunEngine({})
    ap_sc.wait_for_connection()

    ap_sc.aperture.z.set(0, wait=True)

    def move_to_large():
        yield from bps.abs_set(ap_sc, ap_sc.aperture_positions.LARGE)

    with pytest.raises(Exception):
        RE(move_to_large())
