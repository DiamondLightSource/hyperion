from __future__ import annotations

from typing import Any

from dodal.devices.detector import TriggerMode
from dodal.devices.fast_grid_scan import GridScanParams

from artemis.parameters.internal_parameters import InternalParameters


class FGSInternalParameters(InternalParameters):
    experiment_params_type = GridScanParams
    experiment_params: GridScanParams

    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        super().artemis_param_preprocessing(param_dict)
        param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = param_dict["num_images"]
        param_dict["num_images_per_trigger"] = 1
        param_dict["trigger_mode"] = TriggerMode.FREE_RUN
