from enum import Enum

SIM_BEAMLINE = "BL03S"
SIM_INSERTION_PREFIX = "SR03S"
ISPYB_PLAN_NAME = "ispyb_readings"
SIM_ZOCALO_ENV = "dev_artemis"
DEFAULT_EXPERIMENT_TYPE = "grid_scan"
BEAMLINE_PARAMETER_PATHS = {
    "i03": "/dls_sw/i03/software/daq_configuration/domain/beamlineParameters",
    "s03": "src/artemis/parameters/tests/test_data/test_beamline_parameters.txt",
}

PARAMETER_VERSION = 0.2
SIM_ISPYB_CONFIG = "src/artemis/external_interaction/unit_tests/test_config.cfg"
PARAMETER_SCHEMA_DIRECTORY = "src/artemis/parameters/schemas/"

DETECTOR_PARAM_DEFAULTS = {
    "current_energy": 100,
    "exposure_time": 0.1,
    "directory": "/tmp",
    "prefix": "file_name",
    "run_number": 0,
    "detector_distance": 100.0,
    "omega_start": 0.0,
    "omega_increment": 0.0,
    "num_images_per_trigger": 1,
    "num_triggers": 2000,
    "use_roi_mode": False,
    "det_dist_to_beam_converter_path": "src/artemis/unit_tests/test_lookup_table.txt",
}


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
