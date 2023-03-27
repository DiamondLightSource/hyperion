from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
from bluesky.run_engine import RunEngine
from dodal import i03

from artemis.device_setup_plans.setup_zebra_for_rotation import setup_zebra_for_rotation

if TYPE_CHECKING:
    from dodal.devices.eiger import DetectorParams, EigerDetector
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra


def create_devices():
    i03.zebra()
    i03.eiger()
    i03.smargon()


DETECTOR_PARAMS = {
    "current_energy": 12650,
    "exposure_time": 0.005,
    "directory": "/dls/i03/data/2023/cm33866-1/bluesky_rotation_test/",
    "prefix": "file_name",
    "run_number": 0,
    "detector_distance": 300.0,
    "omega_start": 0.0,
    "omega_increment": 0.1,
    "num_images": 3600,
    "use_roi_mode": False,
    "det_dist_to_beam_converter_path": "/dls_sw/i03/software/daq_configuration/lookup/DetDistToBeamXYConverter.txt",
}

DIRECTION = -1
OFFSET = 1


def get_plan(detector: EigerDetector, zebra: Zebra, smargon: Smargon):
    # TODO everything to plan so that we can wait on these
    def move_to_start_w_buffer(motors: Smargon, start_angle):
        yield from bps.abs_set(motors.omega.velocity, 100, wait=True)
        yield from bps.abs_set(
            motors.omega, start_angle - (OFFSET * DIRECTION), wait=True
        )

    def move_to_end_w_buffer(motors: Smargon, scan_width):
        yield from bps.rel_set(
            motors.omega, (scan_width + 0.1 + OFFSET) * DIRECTION, wait=True
        )

    def set_speed(motors: Smargon, image_width, exposure_time):
        yield from bps.abs_set(
            motors.omega.velocity, image_width / exposure_time, wait=True
        )

    def real_eiger_stage(eiger: EigerDetector):
        eiger.stage()
        eiger.set_num_triggers_and_captures()

    detector_params = DetectorParams(**DETECTOR_PARAMS)
    try:
        detector.set_detector_parameters(detector_params)

        RE = RunEngine({})
        start_angle = detector_params.omega_start
        scan_width = detector_params.num_images * detector_params.omega_increment
        image_width = detector_params.omega_increment
        exposure_time = detector_params.exposure_time

        print("staging eiger")
        real_eiger_stage(detector)
        print("wait for any previous moves...")
        print(f"setting up zeb w: start_angle={start_angle}, scan_width={scan_width}")
        RE(
            setup_zebra_for_rotation(
                zebra, start_angle=start_angle, scan_width=scan_width
            )
        )
        print(f"moving omega to {start_angle}")

        RE(move_to_start_w_buffer(smargon, start_angle))
        print(
            f"setting rotation speed for image_width, exposure_time {image_width, exposure_time} to {image_width/exposure_time}"
        )
        RE(set_speed(smargon, image_width, exposure_time))
        print("wait for any previous moves...")

        print("done")
        zebra.pc.arm()
        print("arming zebra PC")

        print("done")
        print(f"{'increase' if DIRECTION > 0 else 'decrease'} omega by {scan_width}")
        RE(move_to_end_w_buffer(smargon, scan_width))
    except Exception as e:
        print(e)
    finally:
        zebra.pc.disarm()
        detector.unstage()


def get_plan():
    pass
