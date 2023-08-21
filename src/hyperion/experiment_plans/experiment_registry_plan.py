from __future__ import annotations

from typing import Callable, Union

from dodal.devices.fast_grid_scan import GridScanParams

import src.hyperion.experiment_plans.flyscan_xray_centre_plan as flyscan_xray_centre_plan
import src.hyperion.experiment_plans.rotation_scan_plan as rotation_scan_plan
from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    NullPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
    GridScanWithEdgeDetectParams,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
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
from src.hyperion.experiment_plans import (
    grid_detect_then_xray_centre_plan,
    pin_centre_then_xray_centre_plan,
    stepped_grid_scan_plan,
)


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: dict[str, dict[str, Callable]] = {
    "flyscan_xray_centre": {
        "setup": flyscan_xray_centre_plan.create_devices,
        "internal_param_type": GridscanInternalParameters,
        "experiment_param_type": GridScanParams,
        "callback_collection_type": XrayCentreCallbackCollection,
    },
    "full_grid_scan": {
        "setup": grid_detect_then_xray_centre_plan.create_devices,
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
