from enum import Enum
from typing import Union

from artemis.devices.fast_grid_scan import GridScanParams
from artemis.devices.rotation_scan import RotationScanParams

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "devrmq"
DEFAULT_EXPERIMENT_TYPE = "grid_scan"

PARAMETER_VERSION = 0.1

EXPERIMENT_DICT = {
    "fast_grid_scan": GridScanParams,
    "rotation_scan": RotationScanParams,
}
EXPERIMENT_NAMES = list(EXPERIMENT_DICT.keys())
EXPERIMENT_TYPE_LIST = list(EXPERIMENT_DICT.values())
EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]
SIM_ISPYB_CONFIG = "src/artemis/external_interaction/unit_tests/test_config.cfg"


class Actions(Enum):
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"
    STATUS = "status"


class Status(Enum):
    WARN = "Warn"
    FAILED = "Failed"
    SUCCESS = "Success"
    BUSY = "Busy"
    ABORTING = "Aborting"
    IDLE = "Idle"
