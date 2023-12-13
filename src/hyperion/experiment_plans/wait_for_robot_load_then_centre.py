from __future__ import annotations

import json
from typing import TYPE_CHECKING

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.eiger import EigerDetector
from dodal.devices.smargon import Smargon

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
)
from hyperion.experiment_plans.pin_centre_then_xray_centre_plan import (
    pin_tip_centre_then_xray_centre,
)
from hyperion.external_interaction.callbacks.robot_load.ispyb_callback import (
    RobotLoadISPyBCallback,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import ROBOT_LOAD_PLAN
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


def wait_for_smargon_not_disabled(smargon: Smargon, timeout=60):
    LOGGER.info("Waiting for smargon enabled")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        smargon_disabled = yield from bps.rd(smargon.disabled)
        if not smargon_disabled:
            LOGGER.info("Smargon now enabled")
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise TimeoutError(
        "Timed out waiting for smargon to become enabled after robot load"
    )


def wait_for_robot_load_then_centre_plan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: WaitForRobotLoadThenCentreInternalParameters,
):
    @bpp.subs_decorator(RobotLoadISPyBCallback())
    @bpp.set_run_key_decorator(ROBOT_LOAD_PLAN)
    @bpp.run_decorator(
        md={
            "subplan_name": ROBOT_LOAD_PLAN,
            "hyperion_internal_parameters": parameters.json(),
            "activate_callbacks": [
                "RobotLoadISPyBCallback",
            ],
        }
    )
    def wait_for_robot_load_and_take_snapshots():
        # Move backlight in

        yield from wait_for_smargon_not_disabled(composite.smargon)

        # Take snapshot

    yield from wait_for_robot_load_and_take_snapshots()

    params_dict = json.loads(parameters.json())
    pin_centre_params = PinCentreThenXrayCentreInternalParameters(**params_dict)
    yield from pin_tip_centre_then_xray_centre(composite, pin_centre_params)


def wait_for_robot_load_then_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: WaitForRobotLoadThenCentreInternalParameters,
) -> MsgGenerator:
    eiger: EigerDetector = composite.eiger

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.experiment_params.detector_distance,
        wait_for_robot_load_then_centre_plan(composite, parameters),
    )
