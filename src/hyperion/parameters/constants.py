from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "dev_artemis"
BEAMLINE_PARAMETER_PATHS = {
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


class PinTipSource():
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
