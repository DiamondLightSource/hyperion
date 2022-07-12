from bluesky import RunEngine
from ophyd.sim import det, motor
from bluesky.plans import scan
from bluesky.callbacks import LiveTable
from bluesky.callbacks import LiveFit
from bluesky.callbacks.fitting import PeakStats

ps = PeakStats('motor', 'det')
RE=RunEngine({})

RE(scan([det], motor, -5, 5, 80), ps)

print("centre",ps['com'])



