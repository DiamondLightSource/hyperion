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

EXPERIMENT_NAMES = ["grid_scan", "rotation_scan"]
EXPERIMENT_TYPE_LIST = [GridScanParams, RotationScanParams]
EXPERIMENT_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))
EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]
SIM_ISPYB_CONFIG = "src/artemis/external_interaction/unit_tests/test_config.cfg"


class Actions(Enum):
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"


class Status(Enum):
    WARN = "Warn"
    FAILED = "Failed"
    SUCCESS = "Success"
    BUSY = "Busy"
    ABORTING = "Aborting"
    IDLE = "Idle"
