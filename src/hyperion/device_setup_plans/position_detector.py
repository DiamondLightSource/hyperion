from bluesky import plan_stubs as bps
from dodal.devices.detector.detector_motion import DetectorMotion, ShutterState

from hyperion.log import LOGGER


def set_detector_z_position(
    detector_motion: DetectorMotion, detector_position: float, group=None
):
    LOGGER.info(f"Moving detector to {detector_position} ({group})")
    yield from bps.abs_set(detector_motion.z, detector_position, group=group)


def set_shutter(detector_motion: DetectorMotion, state: ShutterState, group=None):
    LOGGER.info(f"Setting shutter to {state} ({group})")
    yield from bps.abs_set(detector_motion.shutter, int(state), group=group)
