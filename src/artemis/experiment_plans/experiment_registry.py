from typing import Callable, Dict

from artemis.experiment_plans import fast_grid_scan_plan
from artemis.parameters.constants import EXPERIMENT_NAMES


def not_implemented():
    raise NotImplementedError


PLAN_REGISTRY: Dict[str, Dict[str, Callable]] = {
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "run": fast_grid_scan_plan.get_plan,
    },
    "rotation_scan": {
        "setup": not_implemented,
        "run": not_implemented,
    },
}


def validate_registry_against_parameter_model() -> bool:
    for expt in PLAN_REGISTRY.keys():
        if expt not in EXPERIMENT_NAMES:
            return False
    return True


def validate_parameter_model_against_registry() -> bool:
    for expt in EXPERIMENT_NAMES.keys():
        if expt not in PLAN_REGISTRY:
            return False
    return True


def parameter_model_and_plan_registry_consistent() -> bool:
    return (
        validate_parameter_model_against_registry()
        & validate_registry_against_parameter_model()
    )


class PlanNotFound(Exception):
    pass
