import json

from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_detector import (
    DISPLAY_CONFIG,
    ZOOM_PARAMS_FILE,
    OAVConfigParams,
)
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
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.utils.context import device_composite_from_context

OAV_CONFIG_FILE_DEFAULTS = {
    "oav_config_json": OAV_CONFIG_JSON,
    "display_config": DISPLAY_CONFIG,
    "zoom_params_file": ZOOM_PARAMS_FILE,
}


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    """
    GridDetectThenXRayCentreComposite contains all the devices we need, reuse that.
    """
    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def create_parameters_for_grid_detection(
    pin_centre_parameters: PinCentreThenXrayCentreInternalParameters,
) -> GridScanWithEdgeDetectInternalParameters:
    params_json = json.loads(pin_centre_parameters.json())

    grid_detect_and_xray_centre = GridScanWithEdgeDetectInternalParameters(
        **params_json
    )
    LOGGER.info(
        f"Parameters for grid detect and xray centre: {grid_detect_and_xray_centre}"
    )
    return grid_detect_and_xray_centre


def pin_centre_then_xray_centre_plan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinCentreThenXrayCentreInternalParameters,
    oav_config_files=OAV_CONFIG_FILE_DEFAULTS,
):
    """Plan that perfoms a pin tip centre followed by an xray centre to completely
    centre the sample"""
    oav_config_files["oav_config_json"] = parameters.experiment_params.oav_centring_file

    pin_tip_centring_composite = PinTipCentringComposite(
        oav=composite.oav, smargon=composite.smargon, backlight=composite.backlight
    )
    pin_tip_centring_composite.oav.parameters = OAVConfigParams(
        oav_config_files["zoom_params_files"], oav_config_files["display_config"]
    )

    yield from pin_tip_centre_plan(
        pin_tip_centring_composite,
        parameters.experiment_params.tip_offset_microns,
        oav_config_files,
    )
    grid_detect_params = create_parameters_for_grid_detection(parameters)

    oav_params = OAVParameters("xrayCentring", oav_config_files["oav_config_json"])

    yield from detect_grid_and_do_gridscan(
        composite,
        grid_detect_params,
        oav_params,
    )


def pin_tip_centre_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinCentreThenXrayCentreInternalParameters,
) -> MsgGenerator:
    """Starts preparing for collection then performs the pin tip centre and xray centre"""

    eiger: EigerDetector = composite.eiger

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        pin_centre_then_xray_centre_plan(composite, parameters),
    )
