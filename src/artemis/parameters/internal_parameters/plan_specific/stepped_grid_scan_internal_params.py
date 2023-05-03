from __future__ import annotations

from typing import Any

from dodal.devices.stepped_grid_scan import SteppedGridScanParams

from artemis.parameters.internal_parameters import InternalParameters


class SteppedGridScanInternalParameters(InternalParameters):
    experiment_params_type = SteppedGridScanParams
    experiment_params: SteppedGridScanParams

    def artemis_param_preprocessing(self, param_dict: dict[str, Any]):
        super().artemis_param_preprocessing(param_dict)
        param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = param_dict["num_images"]
        param_dict["num_images_per_trigger"] = 1
