from __future__ import annotations

from typing import Any

from dodal.devices.rotation_scan import RotationScanParams

from artemis.parameters.internal_parameters import InternalParameters


class RotationInternalParameters(InternalParameters):
    experiment_params_type = RotationScanParams

    def pre_sorting_translation(self, param_dict: dict[str, Any]):
        super().pre_sorting_translation(param_dict)
        if param_dict["rotation_angle"] == "omega":
            param_dict["omega_increment"] = param_dict["rotation_increment"]
        else:
            param_dict["omega_increment"] = 0
        param_dict["num_triggers"] = 1
        param_dict["num_images_per_trigger"] = param_dict["num_images"]
