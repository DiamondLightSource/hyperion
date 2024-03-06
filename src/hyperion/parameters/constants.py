from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_HARDWARE_READ_PLAN = "ispyb_reading_hardware"
ISPYB_TRANSMISSION_FLUX_READ_PLAN = "ispyb_update_transmission_flux"
NEXUS_READ_PLAN = "nexus_read_plan"
SIM_ZOCALO_ENV = "dev_artemis"

CALLBACK_0MQ_PROXY_PORTS = (5577, 5578)

# this one is for reading
SIM_ISPYB_CONFIG = "tests/test_data/test_config.cfg"
# this one is for making depositions:
DEV_ISPYB_DATABASE_CFG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"

PARAMETER_SCHEMA_DIRECTORY = "src/hyperion/parameters/schemas/"
OAV_REFRESH_DELAY = 0.3

# Plan section names ###################################################################
# Gridscan
GRIDSCAN_OUTER_PLAN = "run_gridscan_move_and_tidy"
GRIDSCAN_AND_MOVE = "run_gridscan_and_move"
GRIDSCAN_MAIN_PLAN = "run_gridscan"
DO_FGS = "do_fgs"
# Rotation scan
ROTATION_OUTER_PLAN = "rotation_scan_with_cleanup"
ROTATION_PLAN_MAIN = "rotation_scan_main"
########################################################################################

# Plan metadata keys ###################################################################
# Gridscan
TRIGGER_ZOCALO_ON = "trigger_zocalo_on"
########################################################################################


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
