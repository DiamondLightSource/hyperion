from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any

import numpy as np
from blueapi.core import BlueskyContext, MsgGenerator
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.DCM import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAV_CONFIG_JSON, OAVParameters
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zocalo import ZocaloResults

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    flyscan_xray_centre,
)
from hyperion.experiment_plans.oav_grid_detection_plan import (
    OavGridDetectionComposite,
    grid_detection_plan,
)
from hyperion.experiment_plans.panda_flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite as FlyScanXRayCentreComposite,
)
from hyperion.experiment_plans.panda_flyscan_xray_centre_plan import (
    panda_flyscan_xray_centre,
)
from hyperion.external_interaction.callbacks.grid_detection_callback import (
    GridDetectionCallback,
)
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)
from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
    GridScanParams,
)
from hyperion.parameters.plan_specific.panda.panda_gridscan_internal_params import (
    PandAGridscanInternalParameters,
    PandAGridScanParams,
)
from hyperion.utils.aperturescatterguard import (
    load_default_aperture_scatterguard_positions_if_unset,
)
from hyperion.utils.context import device_composite_from_context

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
        GridScanWithEdgeDetectInternalParameters,
        GridScanWithEdgeDetectParams,
    )
from dodal.devices.panda_fast_grid_scan import PandAFastGridScan
from ophyd_async.panda import PandA


@dataclasses.dataclass
class GridDetectThenXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    dcm: DCM
    detector_motion: DetectorMotion
    eiger: EigerDetector
    fast_grid_scan: FastGridScan
    flux: Flux
    oav: OAV
    pin_tip_detection: PinTipDetection
    smargon: Smargon
    synchrotron: Synchrotron
    s4_slit_gaps: S4SlitGaps
    undulator: Undulator
    xbpm_feedback: XBPMFeedback
    zebra: Zebra
    zocalo: ZocaloResults
    panda: PandA
    panda_fast_grid_scan: PandAFastGridScan
    robot: BartRobot

    def __post_init__(self):
        """Ensure that aperture positions are loaded whenever this class is created."""
        load_default_aperture_scatterguard_positions_if_unset(
            self.aperture_scatterguard
        )


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def create_parameters_for_flyscan_xray_centre(
    grid_scan_with_edge_params: GridScanWithEdgeDetectInternalParameters,
    grid_parameters: GridScanParams,
) -> GridscanInternalParameters:
    params_json = json.loads(grid_scan_with_edge_params.json())
    params_json["experiment_params"] = json.loads(grid_parameters.json())
    flyscan_xray_centre_parameters = GridscanInternalParameters(**params_json)
    LOGGER.info(f"Parameters for FGS: {flyscan_xray_centre_parameters}")
    return flyscan_xray_centre_parameters


def create_parameters_for_panda_flyscan_xray_centre(
    grid_scan_with_edge_params: GridScanWithEdgeDetectInternalParameters,
    grid_parameters: PandAGridScanParams,
) -> PandAGridscanInternalParameters:
    params_json = json.loads(grid_scan_with_edge_params.json())
    params_json["experiment_params"] = json.loads(grid_parameters.json())
    flyscan_xray_centre_parameters = PandAGridscanInternalParameters(**params_json)
    LOGGER.info(f"Parameters for FGS: {flyscan_xray_centre_parameters}")
    return flyscan_xray_centre_parameters


def detect_grid_and_do_gridscan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: GridScanWithEdgeDetectInternalParameters,
    oav_params: OAVParameters,
):
    assert composite.aperture_scatterguard.aperture_positions is not None
    experiment_params: GridScanWithEdgeDetectParams = parameters.experiment_params

    detector_params = parameters.hyperion_params.detector_params
    snapshot_template = (
        f"{detector_params.prefix}_{detector_params.run_number}_{{angle}}"
    )

    oav_callback = OavSnapshotCallback()
    grid_params_callback = GridDetectionCallback(
        composite.oav.parameters,
        experiment_params.exposure_time,
        experiment_params.set_stub_offsets,
        experiment_params.run_up_distance_mm,
    )

    @bpp.subs_decorator([oav_callback, grid_params_callback])
    def run_grid_detection_plan(
        oav_params,
        snapshot_template,
        snapshot_dir,
    ):
        grid_detect_composite = OavGridDetectionComposite(
            backlight=composite.backlight,
            oav=composite.oav,
            smargon=composite.smargon,
            pin_tip_detection=composite.pin_tip_detection,
        )

        yield from grid_detection_plan(
            grid_detect_composite,
            oav_params,
            snapshot_template,
            snapshot_dir,
            grid_width_microns=experiment_params.grid_width_microns,
        )

    yield from run_grid_detection_plan(
        oav_params,
        snapshot_template,
        experiment_params.snapshot_dir,
    )

    # Hack because GDA only passes 3 values to ispyb
    out_upper_left = np.array(
        oav_callback.out_upper_left[0] + [oav_callback.out_upper_left[1][1]]
    )

    # Hack because the callback returns the list in inverted order
    parameters.hyperion_params.ispyb_params.xtal_snapshots_omega_start = (
        oav_callback.snapshot_filenames[0][::-1]
    )
    parameters.hyperion_params.ispyb_params.xtal_snapshots_omega_end = (
        oav_callback.snapshot_filenames[1][::-1]
    )
    parameters.hyperion_params.ispyb_params.upper_left = out_upper_left

    yield from bps.abs_set(composite.backlight, Backlight.OUT)

    LOGGER.info(
        f"Setting aperture position to {composite.aperture_scatterguard.aperture_positions.SMALL}"
    )
    yield from bps.abs_set(
        composite.aperture_scatterguard,
        composite.aperture_scatterguard.aperture_positions.SMALL,
    )

    flyscan_composite = FlyScanXRayCentreComposite(
        aperture_scatterguard=composite.aperture_scatterguard,
        attenuator=composite.attenuator,
        backlight=composite.backlight,
        eiger=composite.eiger,
        panda_fast_grid_scan=composite.panda_fast_grid_scan,
        flux=composite.flux,
        s4_slit_gaps=composite.s4_slit_gaps,
        smargon=composite.smargon,
        undulator=composite.undulator,
        synchrotron=composite.synchrotron,
        xbpm_feedback=composite.xbpm_feedback,
        zebra=composite.zebra,
        zocalo=composite.zocalo,
        panda=composite.panda,
        fast_grid_scan=composite.fast_grid_scan,
        dcm=composite.dcm,
        robot=composite.robot,
    )

    if parameters.experiment_params.use_panda:
        grid_params = grid_params_callback.get_panda_grid_parameters()

        flyscan_xray_centre_parameters = (
            create_parameters_for_panda_flyscan_xray_centre(parameters, grid_params)
        )

        yield from panda_flyscan_xray_centre(
            flyscan_composite,
            flyscan_xray_centre_parameters,
        )

    else:
        grid_params = grid_params_callback.get_grid_parameters()
        flyscan_xray_centre_parameters = create_parameters_for_flyscan_xray_centre(
            parameters, grid_params
        )

        yield from flyscan_xray_centre(
            flyscan_composite,
            flyscan_xray_centre_parameters,
        )


def grid_detect_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: Any,
    oav_config: str = OAV_CONFIG_JSON,
) -> MsgGenerator:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    eiger: EigerDetector = composite.eiger

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    oav_params = OAVParameters("xrayCentring", oav_config)

    plan_to_perform = detect_grid_and_do_gridscan(
        composite,
        parameters,
        oav_params,
    )

    return start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.hyperion_params.detector_params.detector_distance,
        plan_to_perform,
    )
