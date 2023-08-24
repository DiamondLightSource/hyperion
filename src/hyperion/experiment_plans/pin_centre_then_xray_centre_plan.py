import dataclasses
import json

from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters
from dodal.devices.smargon import Smargon

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

    yield from pin_tip_centre_plan(
        PinTipCentringComposite(
            oav=composite.oav, smargon=composite.smargon, backlight=composite.backlight
        ),
        parameters.experiment_params.tip_offset_microns,
        oav_config_files,
    )
    grid_detect_params = create_parameters_for_grid_detection(parameters)

    backlight = composite.backlight
    aperture_scattergaurd = composite.aperture_scatterguard
    detector_motion = composite.detector_motion

    oav_params = OAVParameters("xrayCentring", **oav_config_files)

    yield from detect_grid_and_do_gridscan(
        composite,
        grid_detect_params,
        backlight,
        aperture_scattergaurd,
        detector_motion,
        oav_params,
    )


def pin_tip_centre_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinCentreThenXrayCentreInternalParameters,
) -> MsgGenerator:
    """Starts preparing for collection then performs the pin tip centre and xray centre"""

    eiger: EigerDetector = composite.eiger
    attenuator: Attenuator = composite.attenuator

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
        pin_centre_then_xray_centre_plan(composite, parameters),
    )
