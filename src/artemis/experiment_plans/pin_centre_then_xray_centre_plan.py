import json
from typing import Callable

from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS

from artemis.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from artemis.experiment_plans.full_grid_scan import (
    create_devices as full_grid_create_devices,
)
from artemis.experiment_plans.full_grid_scan import (
    get_plan as detect_grid_and_do_gridscan,
)
from artemis.experiment_plans.pin_tip_centring_plan import (
    create_devices as pin_tip_create_devices,
)
from artemis.experiment_plans.pin_tip_centring_plan import pin_tip_centre_plan
from artemis.log import LOGGER
from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from artemis.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)


def create_devices():
    full_grid_create_devices()
    pin_tip_create_devices()


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
    parameters: PinCentreThenXrayCentreInternalParameters,
):
    """Plan that perfoms a pin tip centre followed by an xray centre to completely
    centre the sample"""
    oav_config_files = OAV_CONFIG_FILE_DEFAULTS
    oav_config_files["oav_config_json"] = parameters.experiment_params.oav_centring_file

    yield from pin_tip_centre_plan(
        parameters.experiment_params.tip_offset_microns, oav_config_files
    )
    grid_detect_params = create_parameters_for_grid_detection(parameters)
    yield from detect_grid_and_do_gridscan(grid_detect_params, oav_config_files)


def get_plan(
    parameters: PinCentreThenXrayCentreInternalParameters,
) -> Callable:
    """Starts preparing for collection then performs the pin tip centre and xray centre"""

    eiger: EigerDetector = i03.eiger()
    attenuator: Attenuator = i03.attenuator()

    eiger.set_detector_parameters(parameters.artemis_params.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        attenuator,
        parameters.artemis_params.ispyb_params.transmission_fraction,
        pin_centre_then_xray_centre_plan(parameters),
    )
