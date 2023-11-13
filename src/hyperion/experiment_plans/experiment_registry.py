from __future__ import annotations

from typing import Callable, TypedDict, Union

from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.panda_fast_grid_scan import PandaGridScanParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentParameterBase

import hyperion.experiment_plans.flyscan_xray_centre_plan as flyscan_xray_centre_plan
import hyperion.experiment_plans.panda_flyscan_xray_centre_plan as panda_flyscan_xray_centre_scan
import hyperion.experiment_plans.rotation_scan_plan as rotation_scan_plan
from hyperion.experiment_plans import (
    grid_detect_then_xray_centre_plan,
    pin_centre_then_xray_centre_plan,
    stepped_grid_scan_plan,
    wait_for_robot_load_then_centre_plan,
)
from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
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
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandaGridscanInternalParameters,
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
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
    WaitForRobotLoadThenCentreParams,
)


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


class ExperimentRegistryEntry(TypedDict):
    setup: Callable
    internal_param_type: (
        type[
            GridscanInternalParameters
            | GridScanWithEdgeDetectInternalParameters
            | RotationInternalParameters
            | PinCentreThenXrayCentreInternalParameters
            | SteppedGridScanInternalParameters
            | WaitForRobotLoadThenCentreInternalParameters
        ]
    )
    experiment_param_type: type[AbstractExperimentParameterBase]
    callback_collection_type: type[AbstractPlanCallbackCollection]


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams, SteppedGridScanParams]
PLAN_REGISTRY: dict[str, ExperimentRegistryEntry] = {
    "panda_flyscan_xray_centre": {
        "setup": panda_flyscan_xray_centre_scan.create_devices,
        "internal_param_type": PandaGridscanInternalParameters,
        "experiment_param_type": PandaGridScanParams,
        "callback_collection_type": XrayCentreCallbackCollection,
    },
    "flyscan_xray_centre": {
        "setup": flyscan_xray_centre_plan.create_devices,
        "internal_param_type": GridscanInternalParameters,
        "experiment_param_type": GridScanParams,
        "callback_collection_type": XrayCentreCallbackCollection,
    },
    "grid_detect_then_xray_centre": {
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
        "internal_param_type": SteppedGridScanInternalParameters,
        "experiment_param_type": SteppedGridScanParams,
        "callback_collection_type": NullPlanCallbackCollection,
    },
    "wait_for_robot_load_then_centre": {
        "setup": wait_for_robot_load_then_centre_plan.create_devices,
        "internal_param_type": WaitForRobotLoadThenCentreInternalParameters,
        "experiment_param_type": WaitForRobotLoadThenCentreParams,
        "callback_collection_type": NullPlanCallbackCollection,
    },
}
EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
EXPERIMENT_TYPE_LIST = [p["experiment_param_type"] for p in PLAN_REGISTRY.values()]
EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
