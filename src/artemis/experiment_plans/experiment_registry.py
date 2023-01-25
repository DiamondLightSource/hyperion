from typing import Callable, Dict

from artemis.experiment_plans import fast_grid_scan_plan

PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "run": fast_grid_scan_plan.get_plan,
    }
}


class PlanNotFound(Exception):
    pass
