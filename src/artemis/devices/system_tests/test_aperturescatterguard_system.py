import bluesky.plan_stubs as bps
import pytest
from bluesky.callbacks import CallbackBase
from bluesky.run_engine import RunEngine

from artemis.devices.aperturescatterguard import (
    AperturePositions,
    ApertureScatterguard,
    InvalidApertureMove,
)
from artemis.parameters import I03_BEAMLINE_PARAMETER_PATH, GDABeamlineParameters


@pytest.fixture
def ap_sg():
    ap_sg = ApertureScatterguard(prefix="BL03S", name="ap_sg")
    ap_sg.load_aperture_positions(
        AperturePositions.from_gda_beamline_params(
            GDABeamlineParameters.from_file(I03_BEAMLINE_PARAMETER_PATH)
        )
    )
    return ap_sg


@pytest.fixture
def move_to_large(ap_sg: ApertureScatterguard):
    yield from bps.abs_set(ap_sg, ap_sg.aperture_positions.LARGE)


@pytest.fixture
def move_to_medium(ap_sg: ApertureScatterguard):
    yield from bps.abs_set(ap_sg, ap_sg.aperture_positions.MEDIUM)


@pytest.fixture
def move_to_small(ap_sg: ApertureScatterguard):
    yield from bps.abs_set(ap_sg, ap_sg.aperture_positions.SMALL)


@pytest.fixture
def move_to_robotload(ap_sg: ApertureScatterguard):
    yield from bps.abs_set(ap_sg, ap_sg.aperture_positions.ROBOT_LOAD)


@pytest.mark.s03
def test_aperturescatterguard_setup(ap_sg: ApertureScatterguard):
    ap_sg.wait_for_connection()
    assert ap_sg.aperture_positions is not None


@pytest.mark.s03
def test_aperturescatterguard_move_in_plan(
    ap_sg: ApertureScatterguard,
    move_to_large,
    move_to_medium,
    move_to_small,
    move_to_robotload,
):
    RE = RunEngine({})
    ap_sg.wait_for_connection()

    ap_sg.aperture.z.set(ap_sg.aperture_positions.LARGE[2], wait=True)

    RE(move_to_large)
    RE(move_to_medium)
    RE(move_to_small)
    RE(move_to_robotload)


@pytest.mark.s03
def test_move_fails_when_not_in_good_starting_pos(
    ap_sg: ApertureScatterguard, move_to_large
):
    RE = RunEngine({})
    ap_sg.wait_for_connection()

    ap_sg.aperture.z.set(0, wait=True)

    with pytest.raises(InvalidApertureMove):
        RE(move_to_large)


class MonitorCallback(CallbackBase):
    # holds on to the most recent time a motor move completed for aperture and
    # scatterguard y

    t_ap_y: float = 0
    t_sg_y: float = 0
    event_docs: list[dict] = []

    def event(self, doc):
        self.event_docs.append(doc)
        if doc["data"].get("ap_sg_aperture_y_motor_done_move") == 1:
            self.t_ap_y = doc["timestamps"].get("ap_sg_aperture_y_motor_done_move")
        if doc["data"].get("ap_sg_scatterguard_y_motor_done_move") == 1:
            self.t_sg_y = doc["timestamps"].get("ap_sg_scatterguard_y_motor_done_move")


@pytest.mark.s03
@pytest.mark.parametrize(
    "pos1,pos2,sg_first",
    [
        ("L", "M", True),
        ("L", "S", True),
        ("L", "R", False),
        ("M", "L", False),
        ("M", "S", True),
        ("M", "R", False),
        ("S", "L", False),
        ("S", "M", False),
        ("S", "R", False),
        ("R", "L", True),
        ("R", "M", True),
        ("R", "S", True),
    ],
)
def test_aperturescatterguard_moves_in_correct_order(
    pos1, pos2, sg_first, ap_sg: ApertureScatterguard
):
    cb = MonitorCallback()
    positions = {
        "L": ap_sg.aperture_positions.LARGE,
        "M": ap_sg.aperture_positions.MEDIUM,
        "S": ap_sg.aperture_positions.SMALL,
        "R": ap_sg.aperture_positions.ROBOT_LOAD,
    }
    pos1 = positions[pos1]
    pos2 = positions[pos2]
    RE = RunEngine({})
    RE.subscribe(cb)

    ap_sg.wait_for_connection()
    ap_sg.aperture.z.set(pos1[2], wait=True)

    def monitor_and_moves():
        yield from bps.open_run()
        yield from bps.monitor(ap_sg.aperture.y.motor_done_move, name="ap_y")
        yield from bps.monitor(ap_sg.scatterguard.y.motor_done_move, name="sg_y")
        yield from bps.mv(ap_sg, pos1)
        yield from bps.mv(ap_sg, pos2)
        yield from bps.close_run()

    RE(monitor_and_moves())

    assert (cb.t_sg_y < cb.t_ap_y) == sg_first
