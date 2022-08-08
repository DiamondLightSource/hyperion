import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine

from src.artemis.devices.aperture import Aperture
from src.artemis.devices.backlight import Backlight
from src.artemis.devices.oav import OAV


def prepare_for_snapshot(backlight: Backlight, aperture: Aperture):
    yield from bps.abs_set(backlight.pos, Backlight.IN, group="A")
    # TODO get from beamlineParameters miniap_y_ROBOT_LOAD
    aperture_y_snapshot_position = 31.40
    aperture.wait_for_connection()
    if (yield from bps.rd(aperture.y)) > aperture_y_snapshot_position:
        yield from bps.abs_set(aperture.y, aperture_y_snapshot_position, group="A")
        yield from bps.wait("A")


def take_snapshot(oav: OAV, snapshot_filename, snapshot_directory):
    oav.wait_for_connection()
    yield from bps.abs_set(oav.snapshot.filename, snapshot_filename)
    yield from bps.abs_set(oav.snapshot.directory, snapshot_directory)
    yield from bps.trigger(oav.snapshot, wait=True)


@bpp.run_decorator()
def snapshot_plan(
    oav: OAV,
    backlight: Backlight,
    aperture: Aperture,
    snapshot_filename: str,
    snapshot_directory: str,
):
    yield from prepare_for_snapshot(backlight, aperture)
    yield from take_snapshot(oav, snapshot_filename, snapshot_directory)


if __name__ == "__main__":
    beamline = "BL03I"
    backlight = Backlight(name="Backlight", prefix=f"{beamline}")
    aperture = Aperture(name="Aperture", prefix=f"{beamline}-MO-MAPT-01:")
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01")
    snapshot_filename = "snapshot"
    snapshot_directory = "."
    RE = RunEngine()
    RE(snapshot_plan(oav, backlight, aperture, snapshot_filename, snapshot_directory))
