from bluesky import RunEngine
from bluesky.plan_stubs import mv, abs_set, wait
from devices.backlight import Backlight

backlight = Backlight(name="Backlight", prefix=f"BL03I")

RE = RunEngine({})

def move_then_wait():
	yield from abs_set(backlight.pos, Backlight.OUT, group='A')
	yield from wait('A')

RE(move_then_wait())
