import bluesky.plan_stubs as bps
from bluesky import RunEngine

from src.artemis.devices.oav import OAV


def take_snapshot_with_grid(oav: OAV, snapshot_filename, snapshot_directory):
    oav.wait_for_connection()
    yield from bps.abs_set(oav.snapshot.top_left_x_signal, 100)
    yield from bps.abs_set(oav.snapshot.top_left_y_signal, 100)
    yield from bps.abs_set(oav.snapshot.box_width_signal, 50)
    yield from bps.abs_set(oav.snapshot.num_boxes_x_signal, 15)
    yield from bps.abs_set(oav.snapshot.num_boxes_y_signal, 10)
    yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
    yield from bps.abs_set(oav.snapshot.directory, snapshot_directory)
    yield from bps.trigger(oav.snapshot, wait=True)


def test_grid_overlay():
    beamline = "BL03I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01")
    snapshot_filename = "snapshot"
    snapshot_directory = "."
    RE = RunEngine()
    RE(take_snapshot_with_grid(oav, snapshot_filename, snapshot_directory))
