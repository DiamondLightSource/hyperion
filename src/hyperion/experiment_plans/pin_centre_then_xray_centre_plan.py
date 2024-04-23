from __future__ import annotations

import json

from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAV_CONFIG_JSON, OAVParameters

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
    detect_grid_and_do_gridscan,
)
from hyperion.experiment_plans.pin_tip_centring_plan import (
    PinTipCentringComposite,
    pin_tip_centre_plan,
)
from hyperion.log import LOGGER
from hyperion.parameters.gridscan import (
    GridScanWithEdgeDetect,
    PinTipCentreThenXrayCentre,
)
from hyperion.utils.context import device_composite_from_context


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    """
    GridDetectThenXRayCentreComposite contains all the devices we need, reuse that.
    """
    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def create_parameters_for_grid_detection(
    pin_centre_parameters: PinTipCentreThenXrayCentre,
) -> GridScanWithEdgeDetect:
    params_json = json.loads(pin_centre_parameters.json())
    del params_json["tip_offset_um"]
    grid_detect_and_xray_centre = GridScanWithEdgeDetect(**params_json)
    LOGGER.info(
        f"Parameters for grid detect and xray centre: {grid_detect_and_xray_centre}"
    )
    return grid_detect_and_xray_centre


def pin_centre_then_xray_centre_plan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinTipCentreThenXrayCentre,
    oav_config_file: str = OAV_CONFIG_JSON,
):
    """Plan that perfoms a pin tip centre followed by an xray centre to completely
    centre the sample"""
    oav_config_file = parameters.oav_centring_file

    pin_tip_centring_composite = PinTipCentringComposite(
        oav=composite.oav,
        smargon=composite.smargon,
        backlight=composite.backlight,
        pin_tip_detection=composite.pin_tip_detection,
    )

    yield from pin_tip_centre_plan(
        pin_tip_centring_composite,
        parameters.tip_offset_um,
        oav_config_file,
    )

    grid_detect_params = create_parameters_for_grid_detection(parameters)

    oav_params = OAVParameters("xrayCentring", oav_config_file)

    yield from detect_grid_and_do_gridscan(
        composite,
        grid_detect_params,
        oav_params,
    )


def pin_tip_centre_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinTipCentreThenXrayCentre,
    oav_config_file: str = OAV_CONFIG_JSON,
) -> MsgGenerator:
    """Starts preparing for collection then performs the pin tip centre and xray centre"""

    eiger: EigerDetector = composite.eiger

    eiger.set_detector_parameters(parameters.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.detector_params.detector_distance,
        pin_centre_then_xray_centre_plan(composite, parameters, oav_config_file),
    )
