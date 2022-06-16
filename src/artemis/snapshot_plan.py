from bluesky import RunEngine
from bluesky.plan_stubs import mv, abs_set, wait
from devices.backlight import Backlight
from devices.aperture import Aperture

backlight = Backlight(name="Backlight", prefix="BL03I")
aperture = Aperture(name="Aperture", prefix="BL03I")
aperture.wait_for_connection()

RE = RunEngine({})

def prepare_for_snapshot():
	yield from abs_set(backlight.pos, Backlight.IN, group='A')
	# TODO get from beamlineParameters
	miniap_y_ROBOT_LOAD = 31.40
	if aperture.y.position > miniap_y_ROBOT_LOAD:
		yield from abs_set(aperture.y, miniap_y_ROBOT_LOAD, group='A')
	yield from wait('A')


RE(prepare_for_snapshot())
