import bluesky.plan_stubs as bps
import pytest
from bluesky import RunEngine

from artemis.devices.oav.oav_detector import OAV

TEST_GRID_TOP_LEFT_X = 100
TEST_GRID_TOP_LEFT_Y = 100
TEST_GRID_BOX_WIDTH = 25
TEST_GRID_NUM_BOXES_X = 5
TEST_GRID_NUM_BOXES_Y = 6


def take_snapshot_with_grid(oav: OAV, snapshot_filename, snapshot_directory):
    oav.wait_for_connection()
    yield from bps.abs_set(oav.snapshot.top_left_x_signal, TEST_GRID_TOP_LEFT_X)
    yield from bps.abs_set(oav.snapshot.top_left_y_signal, TEST_GRID_TOP_LEFT_Y)
    yield from bps.abs_set(oav.snapshot.box_width_signal, TEST_GRID_BOX_WIDTH)
    yield from bps.abs_set(oav.snapshot.num_boxes_x_signal, TEST_GRID_NUM_BOXES_X)
    yield from bps.abs_set(oav.snapshot.num_boxes_y_signal, TEST_GRID_NUM_BOXES_Y)
    yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
    yield from bps.abs_set(oav.snapshot.directory, snapshot_directory)
    yield from bps.trigger(oav.snapshot, wait=True)


@pytest.mark.skip(reason="Don't want to actually take snapshots during testing.")
def test_grid_overlay():
    beamline = "BL03I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01")
    snapshot_filename = "snapshot"
    snapshot_directory = "."
    RE = RunEngine()
    RE(take_snapshot_with_grid(oav, snapshot_filename, snapshot_directory))
