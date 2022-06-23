from bluesky import RunEngine
from devices.I03Smargon import I03Smargon
from devices.backlight import Backlight
from devices.BeamStop import BeamStop
from devices.miniap import MiniAperture
from devices.FluorescenceDetector import FluorescenceDetector
from devices.Scintillator import Scintillator
from devices.Scatterguard import Scatterguard
from devices.GonioLowerStages import GonioLowerStages
from devices.Cryostream import Cryo
from devices.CTAB import CTAB
from bluesky.plan_stubs import mv, null
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from datetime import datetime

# Moves beamline motors to known positions prior to UDC start. Logic order: Check cryo backpressure and temperature; Move scintillator stick out safely; Move fluorescence detector out and set CTAB to 0; Move Chi to 0; Move rest of Smargon and lower gonio stages to 0; Move beamstop to robot load position; Move miniap safely to robot load position; move cryostream in.

sgon = I03Smargon(name="I03Smargon", prefix="BL03I")
backlight = Backlight(name="Backlight", prefix="BL03I")
mapt = MiniAperture(name="MiniAperture", prefix="BL03I")
bs = BeamStop(name="BeamStop", prefix="BL03I")
fluo = FluorescenceDetector(name="FluorescenceDetector", prefix="BL03I")
scin = Scintillator(name="Scintillator", prefix="BL03I")
sg = Scatterguard(name="Scatterguard", prefix="BL03I")
gonp = GonioLowerStages(name="GonioLowerStages", prefix="BL03I")
cryo = Cryo(name="Cryo", prefix="BL03I")
ctab = CTAB(name="CTAB", prefix="BL03I")



sgon.wait_for_connection()
backlight.wait_for_connection()
mapt.wait_for_connection()
bs.wait_for_connection()
fluo.wait_for_connection()
scin.wait_for_connection()
sg.wait_for_connection()
gonp.wait_for_connection()
cryo.wait_for_connection()
ctab.wait_for_connection()


IN=1
OUT=0

######default state for I03. The safe psitions should be read from a central parameter file

RE=RunEngine({})

def make_scin_safe():

	if (scin.y.position < 0.016 and scin.z.position < 0.1):
		pass
	else:
		yield from bps.mv(scin.y, 0.015, mapt.x, -4.91, sg.x, -4.75) 
		yield from bps.mv(scin.z, 0.1)

def put_bs_in():
	if (bs.z.position >25 and bs.y.position > 25):
		pass
	else:
		yield from bps.mv(bs.z, 30)
		yield from bps.mv(bs.y, 45, bs.x, 1.6) 
		

def check_temp():
	cryo_temp = cryo.temp.get()
	if cryo_temp > 110:
		print ("temperature too high - ",cryo_temp)  # TODO abort here
	else:
		pass
	yield from null()

def check_backpressure():
	cryo_backpressure = cryo.backpress.get()
	if cryo_backpressure > 0.1:
		print ("Backpressure too high - ",cryo_backpressure)  # TODO abort here
	else:
		pass
	yield from null()



def move_to_default_UDC_state():			# TODO add energy change
	
	#basic checks, abort if fail
	yield from check_backpressure()
	yield from check_temp()
	# TODO check HC1 mode, plate mode

	#basic checks done, move to known positions safely
	yield from make_scin_safe()
	yield from bps.mv(fluo.pos, OUT) #, ctab.inboard_y, 0, ctab.outboard_y, 0, ctab.upstream_y, 0, ctab.downstream_x, 0, ctab.upstream_x, 0) 
	yield from bps.mv(sgon.chi, 0)
	yield from bps.mv(sgon.x, 0, sgon.y, 0, sgon.z, 0, sgon.phi, 0, sgon.omega, 0, gonp.x, 0, gonp.z, 0) 
	yield from put_bs_in()
	yield from bps.mv(mapt.z, 15.8)
	yield from bps.mv(mapt.x, 2.564, mapt.y, 31.4)
	yield from bps.mv(cryo.course, IN, cryo.fine, IN)
	
	

RE(move_to_default_UDC_state())
	
	


