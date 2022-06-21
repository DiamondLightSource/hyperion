from bluesky import RunEngine
from devices.QBPM1 import QBPM1
from devices.DCM import DCM
from bluesky.callbacks import LiveTable
from bluesky.callbacks.fitting import PeakStats

import bluesky.plans as bp
import bluesky.plan_stubs as bps


qbpm1 = QBPM1(name="QBPM1", prefix="BL03I")
dcm = DCM(name="DCM", prefix="BL03I")

qbpm1.wait_for_connection()
dcm.wait_for_connection()

RE=RunEngine({})

ps = PeakStats('DCM_pitch', 'QBPM1_intensity')

RE(bp.rel_scan([qbpm1.intensity], dcm.pitch, -0.075, 0.075, 30),ps) 	#	LiveTable([dcm.pitch,qbpm1.intensity]))

print("centre",ps['com'])

RE(bps.mv(dcm.pitch, ps['com']))
