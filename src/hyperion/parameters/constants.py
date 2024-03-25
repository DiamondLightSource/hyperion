import os
from enum import Enum

from pydantic.dataclasses import dataclass

TEST_MODE = os.environ.get("HYPERION_TEST_MODE")


@dataclass(frozen=True)
class SimConstants:
    BEAMLINE = "BL03S"
    INSERTION_PREFIX = "SR03S"
    ZOCALO_ENV = "dev_artemis"
    # this one is for unit tests
    ISPYB_CONFIG = "tests/test_data/test_config.cfg"
    # this one is for system tests
    DEV_ISPYB_DATABASE_CFG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


@dataclass(frozen=True)
class PlanNameConstants:
    # For callbacks to use
    NEXUS_READ = "nexus_read_plan"
    ISPYB_HARDWARE_READ = "ispyb_reading_hardware"
    ISPYB_TRANSMISSION_FLUX_READ = "ispyb_update_transmission_flux"
    ZOCALO_HW_READ = "zocalo_read_hardware_plan"
    # Gridscan
    GRIDSCAN_OUTER = "run_gridscan_move_and_tidy"
    GRIDSCAN_AND_MOVE = "run_gridscan_and_move"
    GRIDSCAN_MAIN = "run_gridscan"
    DO_FGS = "do_fgs"
    # Rotation scan
    ROTATION_OUTER = "rotation_scan_with_cleanup"
    ROTATION_MAIN = "rotation_scan_main"


@dataclass(frozen=True)
class HardwareConstants:
    OAV_REFRESH_DELAY = 0.3


@dataclass(frozen=True)
class TriggerConstants:
    ZOCALO = "trigger_zocalo_on"


@dataclass(frozen=True)
class GridscanParamConstants:
    WIDTH_UM = 20.0
    EXPOSURE_TIME_S = 0.02
    USE_ROI = True
    APERTURE_SIZE = 20.0


@dataclass(frozen=True)
class DetectorParamConstants:
    BEAM_XY_LUT_PATH = (
        "/dls_sw/i03/software/daq_configuration/lookup/DetDistToBeamXYConverter.txt"
    )


@dataclass(frozen=True)
class ExperimentParamConstants:
    GRIDSCAN = GridscanParamConstants()
    DETECTOR = DetectorParamConstants()


@dataclass(frozen=True)
class I03Constants:
    BEAMLINE = "BL03S" if TEST_MODE else "BL03I"
    INSERTION_PREFIX = "SR03S" if TEST_MODE else "SR03I"
    BASE_DATA_DIR = "/tmp/dls/i03/data/" if TEST_MODE else "/dls/i03/data/"


@dataclass(frozen=True)
class HyperionConstants:
    SIM = SimConstants()
    PLAN = PlanNameConstants()
    HARDWARE = HardwareConstants()
    TRIGGER = TriggerConstants()
    PARAM = ExperimentParamConstants()
    I03 = I03Constants()
    CALLBACK_0MQ_PROXY_PORTS = (5577, 5578)
    PARAMETER_SCHEMA_DIRECTORY = "src/hyperion/parameters/schemas/"


CONST = HyperionConstants()


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
