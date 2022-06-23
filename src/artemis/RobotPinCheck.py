from bluesky import RunEngine
from devices.Robot import BART
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.callbacks import LiveTable

robot = BART(name="BART", prefix="BL03I")

robot.wait_for_connection()


RE=RunEngine({})


def check_pin_mounted_on_gonio():
	check_1 = robot.GonioPinSensor.get()
	bps.sleep(0.5)
	check_2 = robot.GonioPinSensor.get()
	if (check_1 * check_2 == 1):
		gonio_status = 1
		print ("Pin mounted")
	else:
		gonio_status = 0
		print ("Goniometer clear")


check_pin_mounted_on_gonio()





