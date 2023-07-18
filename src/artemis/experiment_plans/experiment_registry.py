from __future__ import annotations

from typing import Callable

from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.stepped_grid_scan import SteppedGridScanParams

from artemis.experiment_plans import (
    fast_grid_scan_plan,
    full_grid_scan,
<<<<<<< HEAD
    stepped_grid_scan_plan,
)
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
=======
    rotation_scan_plan,
>>>>>>> origin/main
)
from artemis.external_interaction.callbacks.abstract_plan_callback_collection import (
    NullPlanCallbackCollection,
)
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
    GridScanWithEdgeDetectParams,
)
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)
from artemis.parameters.internal_parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
)


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


<<<<<<< HEAD
EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
=======
PLAN_REGISTRY: dict[str, dict[str, Callable]] = {
>>>>>>> origin/main
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "run": fast_grid_scan_plan.get_plan,
        "internal_param_type": FGSInternalParameters,
        "experiment_param_type": GridScanParams,
        "callback_collection_type": FGSCallbackCollection,
    },
    "full_grid_scan": {
        "setup": full_grid_scan.create_devices,
        "run": full_grid_scan.get_plan,
        "internal_param_type": GridScanWithEdgeDetectInternalParameters,
        "experiment_param_type": GridScanWithEdgeDetectParams,
        "callback_collection_type": NullPlanCallbackCollection,
    },
    "rotation_scan": {
        "setup": rotation_scan_plan.create_devices,
        "run": rotation_scan_plan.get_plan,
        "internal_param_type": RotationInternalParameters,
        "experiment_param_type": RotationScanParams,
        "callback_collection_type": RotationCallbackCollection,
    },
    "stepped_grid_scan": {
        "setup": stepped_grid_scan_plan.create_devices,
        "run": stepped_grid_scan_plan.get_plan,
        "internal_param_type": SteppedGridScanInternalParameters,
        "experiment_param_type": SteppedGridScanParams,
    },
}
EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
EXPERIMENT_TYPE_LIST = [p["experiment_param_type"] for p in PLAN_REGISTRY.values()]
EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
