from __future__ import annotations

from typing import Callable, Dict, Union

from dodal.devices.fast_grid_scan import GridScanParams

from artemis.experiment_plans import fast_grid_scan_plan, full_grid_scan
from artemis.external_interaction.callbacks.abstract_plan_callback_collection import (
    NullPlanCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)
from artemis.parameters.internal_parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
    GridScanWithEdgeDetectParams,
)
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


# EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]
# PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
#     "fast_grid_scan": {
#         "setup": fast_grid_scan_plan.create_devices,
#         "run": fast_grid_scan_plan.get_plan,
#         "internal_param_type": FGSInternalParameters,
#         "experiment_param_type": GridScanParams,
#     },
#     "rotation_scan": {
#         "setup": do_nothing,
#         "run": not_implemented,
#         "internal_param_type": RotationInternalParameters,
#         "experiment_param_type": RotationScanParams,
#     },
# }
# EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
# EXPERIMENT_TYPE_LIST = [p["experiment_param_type"] for p in PLAN_REGISTRY.values()]
# EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
