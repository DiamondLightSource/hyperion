from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dataclasses_json import DataClassJsonMixin
from dodal.devices.detector import TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

from artemis.parameters.internal_parameters import InternalParameters


@dataclass
class GridScanWithEdgeDetectParams(DataClassJsonMixin, AbstractExperimentParameterBase):
    """
    Holder class for the parameters of a grid scan that uses edge detection to detect the grid.
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance: float
    omega_start: float

    def get_num_images(self):
        return None


class GridScanWithEdgeDetectInternalParameters(InternalParameters):
    experiment_params_type = GridScanWithEdgeDetectParams

    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        super().artemis_param_preprocessing(param_dict)
        param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = None
        param_dict["num_images_per_trigger"] = 1
        param_dict["trigger_mode"] = TriggerMode.FREE_RUN
