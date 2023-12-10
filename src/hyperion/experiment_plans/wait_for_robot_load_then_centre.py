from __future__ import annotations

import json
from typing import TYPE_CHECKING

from blueapi.core import BlueskyContext, MsgGenerator

from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
)
from hyperion.experiment_plans.pin_centre_then_xray_centre_plan import (
    pin_tip_centre_then_xray_centre,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
        WaitForRobotLoadThenCentreInternalParameters,
    )


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    from hyperion.utils.context import device_composite_from_context

    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def wait_for_robot_load_then_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: WaitForRobotLoadThenCentreInternalParameters,
) -> MsgGenerator:
    # Start arming the detector

    # Move backlight in

    # Wait for robot to finish moving

    # Take snapshot

    # Put robot load into ispyb

    # Do centering
    params_json = json.loads(parameters.json())
    pin_centre_params = PinCentreThenXrayCentreInternalParameters(**params_json)
    yield from pin_tip_centre_then_xray_centre(composite, pin_centre_params)
