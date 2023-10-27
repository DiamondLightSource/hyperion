from __future__ import annotations

from typing import Callable, Union

from dodal.devices.fast_grid_scan import GridScanParams

import hyperion.experiment_plans.vmxm_flyscan_xray_centre_plan as vmxm_flyscan_xray_centre_plan
import hyperion.experiment_plans.rotation_scan_plan as rotation_scan_plan
from hyperion.experiment_plans import (
    grid_detect_then_xray_centre_plan,
    pin_centre_then_xray_centre_plan,
    stepped_grid_scan_plan,
)
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


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: dict[str, dict[str, Callable]] = {
    "vmxm_flyscan_xray_centre": {
        "setup": vmxm_flyscan_xray_centre_plan.create_devices,
        "internal_param_type": GridscanInternalParameters,
        "experiment_param_type": GridScanParams,
        "callback_collection_type": XrayCentreCallbackCollection,
    },
}
EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
EXPERIMENT_TYPE_LIST = [p["experiment_param_type"] for p in PLAN_REGISTRY.values()]
EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
