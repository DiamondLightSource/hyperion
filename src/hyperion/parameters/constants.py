from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_HARDWARE_READ_PLAN = "ispyb_reading_hardware"
ISPYB_TRANSMISSION_FLUX_READ_PLAN = "ispyb_update_transmission_flux"
SIM_ZOCALO_ENV = "dev_artemis"

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


class PinTipSource:
    """
    Two possible sources for how to get pin-tip information from an OAV.

    AD_MXSC_PLUGIN:
        The calculations for pin-tip detection run in an ADPython areadetector
        plugin, configured as part of the areadetector plugin chain in EPICS.
        The pin tip location is being constantly calculated in the background.
    OPHYD:
        The calculations are done in an ophyd device, which pulls a camera frame
        via PVAccess and then calculates the pin tip location locally, only when
        requested.
        Due to using PVAccess, this can only work on the beamline control machine,
        not from a developer machine.
    """

    AD_MXSC_PLUGIN = 0
    OHPYD_DEVICE = 1


# Hack: currently default to using MXSC plugin.
# Eventually probably want this passed in as a parameter,
# or be confident enough in ophyd device that we can just use
# that unconditionally.
PIN_TIP_SOURCE = PinTipSource.AD_MXSC_PLUGIN
