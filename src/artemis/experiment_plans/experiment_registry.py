from __future__ import annotations

from typing import Callable, Dict, Union

from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.stepped_grid_scan import SteppedGridScanParams

from artemis.experiment_plans import fast_grid_scan_plan, stepped_grid_scan_plan
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
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


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "run": fast_grid_scan_plan.get_plan,
        "internal_param_type": FGSInternalParameters,
        "experiment_param_type": GridScanParams,
    },
    "rotation_scan": {
        "setup": do_nothing,
        "run": not_implemented,
        "internal_param_type": RotationInternalParameters,
        "experiment_param_type": RotationScanParams,
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
