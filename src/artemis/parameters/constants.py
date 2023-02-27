from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "devrmq"
DEFAULT_EXPERIMENT_TYPE = "grid_scan"
I03_BEAMLINE_PARAMETER_PATH = (
    "/dls_sw/i03/software/daq_configuration/domain/beamlineParameters"
)
PARAMETER_VERSION = 0.1

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
