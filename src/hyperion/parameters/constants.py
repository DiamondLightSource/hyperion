import os
from enum import Enum

from dodal.devices.detector import EIGER2_X_16M_SIZE
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
    DEV_ISPYB_DATABASE_CFG = "/dls_sw/dasc/mariadb/credentials/ispyb-hyperion-dev.cfg"


@dataclass(frozen=True)
class PlanNameConstants:
    # Robot load subplan
    ROBOT_LOAD = "robot_load"
    # Gridscan
    GRID_DETECT_AND_DO_GRIDSCAN = "grid_detect_and_do_gridscan"
    GRID_DETECT_INNER = "grid_detect"
    GRIDSCAN_OUTER = "run_gridscan_move_and_tidy"
    GRIDSCAN_AND_MOVE = "run_gridscan_and_move"
    GRIDSCAN_MAIN = "run_gridscan"
    DO_FGS = "do_fgs"
    # Rotation scan
    ROTATION_MULTI = "multi_rotation_wrapper"
    ROTATION_OUTER = "rotation_scan_with_cleanup"
    ROTATION_MAIN = "rotation_scan_main"


@dataclass(frozen=True)
class PlanGroupCheckpointConstants:
    # For places to synchronise / stop and wait in plans, use as bluesky group names
    # Gridscan
    GRID_READY_FOR_DC = "ready_for_data_collection"
    MOVE_GONIO_TO_START = "move_gonio_to_start"


@dataclass(frozen=True)
class DocDescriptorNames:
    # Robot load event descriptor
    ROBOT_LOAD = "robot_load"
    # For callbacks to use
    OAV_ROTATION_SNAPSHOT_TRIGGERED = "rotation_snapshot_triggered"
    OAV_GRID_SNAPSHOT_TRIGGERED = "snapshot_to_ispyb"
    HARDWARE_READ_PRE = "read_hardware_for_callbacks_pre_collection"
    HARDWARE_READ_DURING = "read_hardware_for_callbacks_during_collection"
    ZOCALO_HW_READ = "zocalo_read_hardware_plan"


@dataclass(frozen=True)
class HardwareConstants:
    OAV_REFRESH_DELAY = 0.3
    PANDA_FGS_RUN_UP_DEFAULT = 0.17
    CRYOJET_MARGIN_MM = 0.2


@dataclass(frozen=True)
class TriggerConstants:
    ZOCALO = "trigger_zocalo_on"


@dataclass(frozen=True)
class GridscanParamConstants:
    WIDTH_UM = 600.0
    EXPOSURE_TIME_S = 0.02
    USE_ROI = True
    BOX_WIDTH_UM = 20.0
    OMEGA_1 = 0.0
    OMEGA_2 = 90.0


@dataclass(frozen=True)
class DetectorParamConstants:
    BEAM_XY_LUT_PATH = (
        "tests/test_data/test_det_dist_converter.txt"
        if TEST_MODE
        else "/dls_sw/i03/software/daq_configuration/lookup/DetDistToBeamXYConverter.txt"
    )


@dataclass(frozen=True)
class ExperimentParamConstants:
    DETECTOR = DetectorParamConstants()
    GRIDSCAN = GridscanParamConstants()


_test_oav_file = "tests/test_data/test_OAVCentring.json"
_live_oav_file = "/dls_sw/i03/software/daq_configuration/json/OAVCentring_hyperion.json"


@dataclass(frozen=True)
class I03Constants:
    BASE_DATA_DIR = "/tmp/dls/i03/data/" if TEST_MODE else "/dls/i03/data/"
    BEAMLINE = "BL03S" if TEST_MODE else "BL03I"
    DETECTOR = EIGER2_X_16M_SIZE
    INSERTION_PREFIX = "SR03S" if TEST_MODE else "SR03I"
    OAV_CENTRING_FILE = _test_oav_file if TEST_MODE else _live_oav_file
    SHUTTER_TIME_S = 0.06
    USE_PANDA_FOR_GRIDSCAN = False
    USE_GPU_FOR_GRIDSCAN_ANALYSIS = False
    THAWING_TIME = 20


@dataclass(frozen=True)
class HyperionConstants:
    HARDWARE = HardwareConstants()
    I03 = I03Constants()
    PARAM = ExperimentParamConstants()
    PLAN = PlanNameConstants()
    WAIT = PlanGroupCheckpointConstants()
    SIM = SimConstants()
    TRIGGER = TriggerConstants()
    CALLBACK_0MQ_PROXY_PORTS = (5577, 5578)
    DESCRIPTORS = DocDescriptorNames()
    CONFIG_SERVER_URL = (
        "http://fake-url-not-real"
        if TEST_MODE
        else "https://daq-config.diamond.ac.uk/api"
    )
    GRAYLOG_PORT = 12232
    PARAMETER_SCHEMA_DIRECTORY = "src/hyperion/parameters/schemas/"
    ZOCALO_ENV = "dev_artemis" if TEST_MODE else "artemis"


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
