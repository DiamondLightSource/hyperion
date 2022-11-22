from typing import Callable, Dict

from artemis.experiment_plans import fast_grid_scan_plan

PLAN_REGISTRY: Dict[str, Callable] = {"fast_grid_scan": fast_grid_scan_plan.get_plan}
