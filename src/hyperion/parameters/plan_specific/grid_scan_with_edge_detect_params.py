from __future__ import annotations

from typing import Any

import numpy as np
from dodal.devices.detector import TriggerMode
from dodal.parameters.experiment_parameter_base import AbstractExperimentWithBeamParams
from pydantic import validator

from hyperion.external_interaction.ispyb.ispyb_dataclass import GridscanIspybParams
from hyperion.parameters.internal_parameters import (
    HyperionParameters,
    InternalParameters,
    extract_experiment_params_from_flat_dict,
    extract_hyperion_params_from_flat_dict,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanHyperionParameters,
)


class GridScanWithEdgeDetectParams(AbstractExperimentWithBeamParams):
    """
    Holder class for the parameters of a grid scan that uses edge detection to detect the grid.
    """

    exposure_time: float
    snapshot_dir: str
    detector_distance: float
    omega_start: float

    # This is the correct grid size for single pin
    grid_width_microns: float = 600

    # Whether to set the stub offsets after centering
    set_stub_offsets: bool = False

    # Distance for the smargon to accelerate into the grid and decelerate out of the grid when using the panda
    run_up_distance_mm: float = 0.15

    use_panda: bool = False

    def get_num_images(self):
        return 0


class GridScanWithEdgeDetectInternalParameters(InternalParameters):
    experiment_params: GridScanWithEdgeDetectParams
    hyperion_params: GridscanHyperionParameters

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            **HyperionParameters.Config.json_encoders,
        }

    def __init__(self, **args):
        super().__init__(**args)

    @staticmethod
    def _hyperion_param_key_definitions() -> tuple[list[str], list[str], list[str]]:
        (
            hyperion_param_field_keys,
            detector_field_keys,
            ispyb_field_keys,
        ) = InternalParameters._hyperion_param_key_definitions()
        ispyb_field_keys += list(GridscanIspybParams.__annotations__.keys())
        return hyperion_param_field_keys, detector_field_keys, ispyb_field_keys

    @validator("experiment_params", pre=True)
    def _preprocess_experiment_params(
        cls,
        experiment_params: dict[str, Any],
    ):
        return GridScanWithEdgeDetectParams(
            **extract_experiment_params_from_flat_dict(
                GridScanWithEdgeDetectParams, experiment_params
            )
        )

    @validator("hyperion_params", pre=True)
    def _preprocess_hyperion_params(
        cls, all_params: dict[str, Any], values: dict[str, Any]
    ):
        experiment_params: GridScanWithEdgeDetectParams = values["experiment_params"]
        all_params["num_images"] = experiment_params.get_num_images()
        all_params["position"] = np.array(all_params["position"])
        all_params["omega_increment"] = 0
        all_params["num_triggers"] = all_params["num_images"]
        all_params["num_images_per_trigger"] = 1
        all_params["trigger_mode"] = TriggerMode.FREE_RUN
        all_params["upper_left"] = np.zeros(3, dtype=np.int32)
        return GridscanHyperionParameters(
            **extract_hyperion_params_from_flat_dict(
                all_params, cls._hyperion_param_key_definitions()
            )
        )

    def get_data_shape(self):
        raise TypeError("Data shape does not apply to this type of experiment!")

    def get_scan_points(self):
        raise TypeError("Scan points do not apply to this type of experiment!")
