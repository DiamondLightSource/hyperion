from __future__ import annotations

from typing import Callable, TypedDict, Union

from dodal.devices.fast_grid_scan import GridScanParams
from dodal.devices.panda_fast_grid_scan import PandAGridScanParams
from dodal.parameters.experiment_parameter_base import AbstractExperimentWithBeamParams

import hyperion.experiment_plans.flyscan_xray_centre_plan as flyscan_xray_centre_plan
import hyperion.experiment_plans.panda_flyscan_xray_centre_plan as panda_flyscan_xray_centre_plan
import hyperion.experiment_plans.rotation_scan_plan as rotation_scan_plan
from hyperion.experiment_plans import (
    grid_detect_then_xray_centre_plan,
    pin_centre_then_xray_centre_plan,
    robot_load_then_centre_plan,
)
from hyperion.external_interaction.callbacks.common.callback_util import (
    CallbacksFactory,
    create_gridscan_callbacks,
    create_robot_load_and_centre_callbacks,
    create_rotation_callbacks,
)
from hyperion.parameters.gridscan import (
    GridScanWithEdgeDetect,
    PinTipCentreThenXrayCentre,
    RobotLoadThenCentre,
    ThreeDGridScan,
)
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectParams,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreParams,
)
from hyperion.parameters.plan_specific.robot_load_then_center_params import (
    RobotLoadThenCentreParams,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationScanParams,
)
from hyperion.parameters.rotation import RotationScan


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


class ExperimentRegistryEntry(TypedDict):
    setup: Callable
    internal_param_type: type[
        ThreeDGridScan
        | GridScanWithEdgeDetect
        | RotationScan
        | PinTipCentreThenXrayCentre
        | RobotLoadThenCentre
    ]
    experiment_param_type: type[AbstractExperimentWithBeamParams]
    callbacks_factory: CallbacksFactory


EXPERIMENT_TYPES = Union[GridScanParams, RotationScanParams]
PLAN_REGISTRY: dict[str, ExperimentRegistryEntry] = {
    "panda_flyscan_xray_centre": {
        "setup": panda_flyscan_xray_centre_plan.create_devices,
        "internal_param_type": ThreeDGridScan,
        "experiment_param_type": PandAGridScanParams,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "flyscan_xray_centre": {
        "setup": flyscan_xray_centre_plan.create_devices,
        "internal_param_type": ThreeDGridScan,
        "experiment_param_type": GridScanParams,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "grid_detect_then_xray_centre": {
        "setup": grid_detect_then_xray_centre_plan.create_devices,
        "internal_param_type": GridScanWithEdgeDetect,
        "experiment_param_type": GridScanWithEdgeDetectParams,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "rotation_scan": {
        "setup": rotation_scan_plan.create_devices,
        "internal_param_type": RotationScan,
        "experiment_param_type": RotationScanParams,
        "callbacks_factory": create_rotation_callbacks,
    },
    "pin_tip_centre_then_xray_centre": {
        "setup": pin_centre_then_xray_centre_plan.create_devices,
        "internal_param_type": PinTipCentreThenXrayCentre,
        "experiment_param_type": PinCentreThenXrayCentreParams,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "robot_load_then_centre": {
        "setup": robot_load_then_centre_plan.create_devices,
        "internal_param_type": RobotLoadThenCentre,
        "experiment_param_type": RobotLoadThenCentreParams,
        "callbacks_factory": create_robot_load_and_centre_callbacks,
    },
}
EXPERIMENT_NAMES = list(PLAN_REGISTRY.keys())
EXPERIMENT_TYPE_LIST = [p["experiment_param_type"] for p in PLAN_REGISTRY.values()]
EXPERIMENT_TYPE_DICT = dict(zip(EXPERIMENT_NAMES, EXPERIMENT_TYPE_LIST))


class PlanNotFound(Exception):
    pass
