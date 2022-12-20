import bluesky.plan_stubs as bps
from bluesky import RunEngine
from devices.detector_motion import Det

det = Det(name="Det", prefix="BL03I")

det.wait_for_connection()

RE = RunEngine({})

"""pre robot load requirements, these may need to be split up and called during preceeding tasks for efficiency"""

def check_det_move_allowed():
    """Detector motion is prevented by a collision prevention system that disables power to the motors when an object crosses the robot light curtain. Detector motion can also be prevented directly by the robot when a load operation is underway. This checks both and prints an appropriate error if these restrictions are in place."""
    if det.z_disabled.get() == 0 and det.crate_power.get() == 0:
        pass
    else:
        if det.z_disabled.get() == 1:
            print(
                "Robot move prevented by robot"
            )  # error: abort with message, log and handle properly
        elif det.crate_power.get() == 1:
            print(
                "Detector move prevented by light curtain, lock hutch or manual reset via key"
            )  # error: abort with message, log and handle properly
        else:
            print(
                "Detector movement safe check failed"
            )  # error: abort with message, log and handle properly


def det_move_robot_load():
    """Check detector motion is allowed and then move to a safe distance for robot load."""
    check_det_move_allowed()
    if det.in_robot_load_safe_position.get() == 1:
        pass
    else:
        yield from bps.mv(det.z, 337)  # read det safe position from beamline parameters
        if det.in_robot_load_safe_position.get() == 1:
            pass
        else:
            print(
                "Detector not in safe position for robot approach"
            )  # error: abort with message, log and handle properly


RE(det_move_robot_load())
