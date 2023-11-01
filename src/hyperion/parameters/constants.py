from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
ISPYB_UPDATING_COLLECTION = "ispyb_update_collection"
SIM_ZOCALO_ENV = "dev_artemis"
BEAMLINE_PARAMETER_PATHS = {
    "i04": "/dls_sw/i04/software/gda_versions/gda_9_29/workspace_git/gda-mx.git/configurations/i04-config/scripts/beamlineParameters",
    "i03": "/dls_sw/i03/software/daq_configuration/domain/beamlineParameters",
    "s03": "src/hyperion/parameters/tests/test_data/test_beamline_parameters.txt",
}

# this one is for reading
SIM_ISPYB_CONFIG = "src/hyperion/external_interaction/unit_tests/test_config.cfg"
# this one is for making depositions:
DEV_ISPYB_DATABASE_CFG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"
PARAMETER_SCHEMA_DIRECTORY = "src/hyperion/parameters/schemas/"
OAV_REFRESH_DELAY = 0.3


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
