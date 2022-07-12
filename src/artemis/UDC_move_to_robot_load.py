from bluesky import RunEngine
from devices.I03Smargon import I03Smargon
from devices.backlight import Backlight
from devices.BeamStop import BeamStop
from devices.miniap import MiniAperture
from bluesky.plan_stubs import mv
import bluesky.plan_stubs as bps
import bluesky.plans as bp


sgon = I03Smargon(name="I03Smargon", prefix="BL03I")
backlight = Backlight(name="Backlight", prefix="BL03I")
mapt = MiniAperture(name="MiniAperture", prefix="BL03I")
bs = BeamStop(name="BeamStop", prefix="BL03I")


sgon.wait_for_connection()
backlight.wait_for_connection()
mapt.wait_for_connection()
bs.wait_for_connection()

RE=RunEngine({})

def move_to_robot_load():
	yield from bps.mv(sgon.stub_offset_set, 1)
	yield from bps.mv(sgon.x,0 ,sgon.y,0, sgon.z, 0, sgon.chi, 0, sgon.phi, 0, sgon.omega, 0, backlight.pos, backlight.OUT, mapt.y, 31.4, bs.z, 30)

RE(move_to_robot_load())

