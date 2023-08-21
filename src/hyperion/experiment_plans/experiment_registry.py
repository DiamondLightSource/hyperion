from __future__ import annotations

from typing import Callable, Union

from dodal.devices.fast_grid_scan import GridScanParams

from hyperion.experiment_plans import (
    fast_grid_scan_plan,
    full_grid_scan_plan,
    pin_centre_then_xray_centre_plan,
    rotation_scan_plan,
    stepped_grid_scan_plan,
)
from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    NullPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from hyperion.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from hyperion.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
    GridScanWithEdgeDetectParams,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
    PinCentreThenXrayCentreParams,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
    RotationScanParams,
)
from hyperion.parameters.plan_specific.stepped_grid_scan_internal_params import (
    SteppedGridScanInternalParameters,
    SteppedGridScanParams,
)


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: dict[str, dict[str, Callable]] = {
    "fast_grid_scan": {
        "setup": fast_grid_scan_plan.create_devices,
        "internal_param_type": FGSInternalParameters,
        "experiment_param_type": GridScanParams,
        "callback_collection_type": FGSCallbackCollection,
    },
    "full_grid_scan": {
        "setup": full_grid_scan_plan.create_devices,
        "internal_param_type": GridScanWithEdgeDetectInternalParameters,
        "experiment_param_type": GridScanWithEdgeDetectParams,
        "callback_collection_type": NullPlanCallbackCollection,
    },
    "rotation_scan": {
        "setup": rotation_scan_plan.create_devices,
        "internal_param_type": RotationInternalParameters,
        "experiment_param_type": RotationScanParams,
        "callback_collection_type": RotationCallbackCollection,
    },
    "pin_tip_centre_then_xray_centre": {
        "setup": pin_centre_then_xray_centre_plan.create_devices,
        "internal_param_type": PinCentreThenXrayCentreInternalParameters,
        "experiment_param_type": PinCentreThenXrayCentreParams,
        "callback_collection_type": NullPlanCallbackCollection,
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
