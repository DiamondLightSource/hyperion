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
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    flyscan_xray_centre,
)
from hyperion.experiment_plans.oav_grid_detection_plan import (
    OavGridDetectionComposite,
    grid_detection_plan,
)
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)
from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
    GridScanParams,
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


@dataclasses.dataclass
class GridDetectThenXRayCentreComposite:
    """All devices which are directly or indirectly required by this plan"""

    aperture_scatterguard: ApertureScatterguard
    attenuator: Attenuator
    backlight: Backlight
    detector_motion: DetectorMotion
    eiger: EigerDetector
    fast_grid_scan: FastGridScan
    flux: Flux
    oav: OAV
    smargon: Smargon
    synchrotron: Synchrotron
    s4_slit_gaps: S4SlitGaps
    undulator: Undulator
    zebra: Zebra

    def __post_init__(self):
        """Ensure that aperture positions are loaded whenever this class is created."""
        load_default_aperture_scatterguard_positions_if_unset(
            self.aperture_scatterguard
        )


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def wait_for_det_to_finish_moving(detector: DetectorMotion, timeout=120.0):
    LOGGER.info("Waiting for detector to finish moving")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        detector_state = yield from bps.rd(detector.shutter)
        detector_z_dmov = yield from bps.rd(detector.z.motor_done_move)
        LOGGER.info(f"Shutter state is {'open' if detector_state==1 else 'closed'}")
        LOGGER.info(f"Detector z DMOV is {detector_z_dmov}")
        if detector_state == 1 and detector_z_dmov == 1:
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise TimeoutError("Detector not finished moving")


def create_parameters_for_flyscan_xray_centre(
    grid_scan_with_edge_params: GridScanWithEdgeDetectInternalParameters,
    grid_parameters: GridScanParams,
) -> GridscanInternalParameters:
    params_json = json.loads(grid_scan_with_edge_params.json())
    params_json["experiment_params"] = json.loads(grid_parameters.json())
    flyscan_xray_centre_parameters = GridscanInternalParameters(**params_json)
    LOGGER.info(f"Parameters for FGS: {flyscan_xray_centre_parameters}")
    return flyscan_xray_centre_parameters


def detect_grid_and_do_gridscan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: GridScanWithEdgeDetectInternalParameters,
    oav_params: OAVParameters,
):
    assert composite.aperture_scatterguard.aperture_positions is not None
    experiment_params: GridScanWithEdgeDetectParams = parameters.experiment_params
    grid_params = GridScanParams(dwell_time=experiment_params.exposure_time * 1000)

    detector_params = parameters.hyperion_params.detector_params
    snapshot_template = (
        f"{detector_params.prefix}_{detector_params.run_number}_{{angle}}"
    )

    oav_callback = OavSnapshotCallback()

    @bpp.subs_decorator([oav_callback])
    def run_grid_detection_plan(
        oav_params,
        fgs_params,
        snapshot_template,
        snapshot_dir,
    ):
        grid_detect_composite = OavGridDetectionComposite(
            backlight=composite.backlight,
            oav=composite.oav,
            smargon=composite.smargon,
        )

        yield from grid_detection_plan(
            grid_detect_composite,
            oav_params,
            fgs_params,
            snapshot_template,
            snapshot_dir,
            grid_width_microns=experiment_params.grid_width_microns,
        )

    yield from run_grid_detection_plan(
        oav_params,
        grid_params,
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

    flyscan_xray_centre_parameters = create_parameters_for_flyscan_xray_centre(
        parameters, grid_params
    )

    yield from bps.abs_set(composite.backlight.pos, Backlight.OUT)
    LOGGER.info(
        f"Setting aperture position to {composite.aperture_scatterguard.aperture_positions.SMALL}"
    )
    yield from bps.abs_set(
        composite.aperture_scatterguard,
        composite.aperture_scatterguard.aperture_positions.SMALL,
    )
    yield from wait_for_det_to_finish_moving(composite.detector_motion)

    flyscan_composite = FlyScanXRayCentreComposite(
        aperture_scatterguard=composite.aperture_scatterguard,
        attenuator=composite.attenuator,
        backlight=composite.backlight,
        eiger=composite.eiger,
        fast_grid_scan=composite.fast_grid_scan,
        flux=composite.flux,
        s4_slit_gaps=composite.s4_slit_gaps,
        smargon=composite.smargon,
        undulator=composite.undulator,
        synchrotron=composite.synchrotron,
        zebra=composite.zebra,
    )

    yield from flyscan_xray_centre(
        flyscan_composite,
        flyscan_xray_centre_parameters,
    )


def grid_detect_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: Any,
    oav_param_files: dict = OAV_CONFIG_FILE_DEFAULTS,
) -> MsgGenerator:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    eiger: EigerDetector = composite.eiger
    attenuator: Attenuator = composite.attenuator

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    oav_params = OAVParameters("xrayCentring", **oav_param_files)

    plan_to_perform = detect_grid_and_do_gridscan(
        composite,
        parameters,
        oav_params,
    )

    return start_preparing_data_collection_then_do_plan(
        eiger,
        attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
        plan_to_perform,
    )
