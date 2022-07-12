from bluesky import RunEngine
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.plan_stubs import mv, abs_set, wait, rd, null



from devices.DCM import DCM
from devices.Attenuators import Attenuators
from devices.Sadako import Ring
from devices.FastShutter import FastShutter
from devices.FluorescenceDetector import FluorescenceDetector, Xspress3Mini



RE = RunEngine({})



dcm = DCM(name="DCM", prefix="BL03I")
att = Attenuators(name="Attenuators", prefix="BL03I")
ring = Ring(name="Attenuators")
fshtr = FastShutter(name="FastShutter", prefix="BL03I")
fluo = FluorescenceDetector(name="FluorescenceDetector", prefix="BL03I")
xspress3 = Xspress3Mini(name="Xspress3Mini", prefix="BL03I")


dcm.wait_for_connection()
att.wait_for_connection()
ring.wait_for_connection()
fshtr.wait_for_connection()
fluo.wait_for_connection()
xspress3.wait_for_connection()


def open_fast_shutter():

	yield from bps.mv(fshtr.mode, 0)
	yield from bps.sleep(0.1)
	yield from bps.mv(fshtr.control, 1)


def close_fast_shutter():
	yield from bps.mv(fshtr.control, 0)
	
def set_transmission(target):
	yield from bps.mv(att.target_transmission, target)
	yield from bps.sleep(0.3)
	yield from bps.mv(att.apply_transmission, 1)
	yield from bps.sleep(1)

def get_transmission():
	current_trans = yield from bps.rd(att.applied_transmission)
	print(current_trans)
	

def set_exposure(seconds):
	yield from bps.mv(xspress3.acquire_time, seconds)

def start_file_saving():
	yield from bps.mv(xspress3.capture, 1)
def stop_file_saving()


def set_file_folder(folder):
	yield from bps.mv(xspress3.filepath, folder)
	
def set_file_name(name):
	yield from bps.mv(xspress3.filename, name)

def set_file_number(number):
	yield from bps.mv(xspress3.filenumber, number)
	

	
	






def check_pv():
	check= yield from bps.rd(ring.ring_current)
	print (check)


RE(get_transmission())


