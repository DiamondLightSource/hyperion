from bluesky import RunEngine
from bluesky.plan_stubs import mv, abs_set, wait, rd
from devices.backlight import Backlight
from devices.aperture import Aperture

backlight = Backlight(name="Backlight", prefix="BL03I")
aperture = Aperture(name="Aperture", prefix="BL03I-MO-MAPT-01:")
aperture.wait_for_connection()

RE = RunEngine({})

def prepare_for_snapshot():
	yield from abs_set(backlight.pos, Backlight.IN, group='A')
	# TODO get from beamlineParameters miniap_y_ROBOT_LOAD
	aperture_y_snapshot_position = 31.40
	if (yield from rd(aperture.y)) > aperture_y_snapshot_position:
		yield from abs_set(aperture.y, aperture_y_snapshot_position, group='A')
	yield from wait('A')


RE(prepare_for_snapshot())
