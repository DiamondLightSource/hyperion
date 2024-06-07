from __future__ import annotations

from typing import Callable, TypedDict

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
from hyperion.parameters.rotation import RotationScan


def not_implemented():
    raise NotImplementedError


def do_nothing():
    pass


class ExperimentRegistryEntry(TypedDict):
    setup: Callable
    param_type: type[
        ThreeDGridScan
        | GridScanWithEdgeDetect
        | RotationScan
        | PinTipCentreThenXrayCentre
        | RobotLoadThenCentre
    ]
    callbacks_factory: CallbacksFactory


PLAN_REGISTRY: dict[str, ExperimentRegistryEntry] = {
    "panda_flyscan_xray_centre": {
        "setup": panda_flyscan_xray_centre_plan.create_devices,
        "param_type": ThreeDGridScan,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "flyscan_xray_centre": {
        "setup": flyscan_xray_centre_plan.create_devices,
        "param_type": ThreeDGridScan,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "grid_detect_then_xray_centre": {
        "setup": grid_detect_then_xray_centre_plan.create_devices,
        "param_type": GridScanWithEdgeDetect,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "rotation_scan": {
        "setup": rotation_scan_plan.create_devices,
        "param_type": RotationScan,
        "callbacks_factory": create_rotation_callbacks,
    },
    "pin_tip_centre_then_xray_centre": {
        "setup": pin_centre_then_xray_centre_plan.create_devices,
        "param_type": PinTipCentreThenXrayCentre,
        "callbacks_factory": create_gridscan_callbacks,
    },
    "robot_load_then_centre": {
        "setup": robot_load_then_centre_plan.create_devices,
        "param_type": RobotLoadThenCentre,
        "callbacks_factory": create_robot_load_and_centre_callbacks,
    },
}


class PlanNotFound(Exception):
    pass
