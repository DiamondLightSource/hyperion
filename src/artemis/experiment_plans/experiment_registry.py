from typing import Callable, Dict, Union

from artemis.devices.fast_grid_scan import GridScanParams
from artemis.devices.rotation_scan import RotationScanParams
from artemis.experiment_plans import fast_grid_scan_plan


def not_implemented():
    raise NotImplementedError


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]
PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "run": fast_grid_scan_plan.get_plan,
        "param_type": GridScanParams,
    },
    "rotation_scan": {
        "setup": not_implemented,
        "run": not_implemented,
        "param_type": RotationScanParams,
    },
}
EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
EXPERIMENT_TYPE_LIST = [p["param_type"] for p in PLAN_REGISTRY.values()]
EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
