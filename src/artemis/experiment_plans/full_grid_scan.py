from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List

from bluesky import plan_stubs as bps
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters

from artemis.experiment_plans.fast_grid_scan_plan import (
    create_devices as fgs_create_devices,
)
from artemis.experiment_plans.fast_grid_scan_plan import get_plan as fgs_get_plan
from artemis.experiment_plans.oav_grid_detection_plan import (
    create_devices as oav_create_devices,
)
from artemis.experiment_plans.oav_grid_detection_plan import grid_detection_plan
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.log import LOGGER
from artemis.parameters.beamline_parameters import get_beamline_parameters
from artemis.parameters.plan_specific.fgs_internal_params import GridScanParams

if TYPE_CHECKING:
    from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
        GridScanWithEdgeDetectInternalParameters,
        GridScanWithEdgeDetectParams,
    )


def create_devices():
    fgs_create_devices()
    oav_create_devices()

    aperture_positions = AperturePositions.from_gda_beamline_params(
        get_beamline_parameters()
    )

    i03.detector_motion()
    i03.backlight()
    i03.aperture_scatterguard(aperture_positions)


def wait_for_det_to_finish_moving(detector: DetectorMotion, timeout=120):
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


def detect_grid_and_do_gridscan(
    parameters: GridScanWithEdgeDetectInternalParameters,
    backlight: Backlight,
    eiger: EigerDetector,
    aperture_scatterguard: ApertureScatterguard,
    detector_motion: DetectorMotion,
    oav_params: OAVParameters,
    experiment_params: GridScanWithEdgeDetectParams,
):
    # Start stage with asynchronous arming here
    yield from bps.abs_set(eiger.do_arm, 1, group="arming")

    fgs_params = GridScanParams(dwell_time=experiment_params.exposure_time * 1000)

    detector_params = parameters.artemis_params.detector_params
    snapshot_template = (
        f"{detector_params.prefix}_{detector_params.run_number}_{{angle}}"
    )

    out_snapshot_filenames: List = []
    out_upper_left: Dict = {}

    yield from grid_detection_plan(
        oav_params,
        fgs_params,
        snapshot_template,
        experiment_params.snapshot_dir,
        out_snapshot_filenames,
        out_upper_left,
    )

    parameters.artemis_params.ispyb_params.xtal_snapshots_omega_start = (
        out_snapshot_filenames[0]
    )
    parameters.artemis_params.ispyb_params.xtal_snapshots_omega_end = (
        out_snapshot_filenames[1]
    )
    parameters.artemis_params.ispyb_params.upper_left = out_upper_left

    parameters.experiment_params = fgs_params

    parameters.artemis_params.detector_params.num_triggers = fgs_params.get_num_images()

    LOGGER.info(f"Parameters for FGS: {parameters}")
    subscriptions = FGSCallbackCollection.from_params(parameters)

    yield from bps.abs_set(backlight.pos, Backlight.OUT)
    LOGGER.info(
        f"Setting aperture position to {aperture_scatterguard.aperture_positions.SMALL}"
    )
    yield from bps.abs_set(
        aperture_scatterguard, aperture_scatterguard.aperture_positions.SMALL
    )
    yield from wait_for_det_to_finish_moving(detector_motion)

    yield from fgs_get_plan(parameters, subscriptions)


def get_plan(
    parameters: GridScanWithEdgeDetectInternalParameters,
    oav_param_files: dict = OAV_CONFIG_FILE_DEFAULTS,
) -> Callable:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    backlight: Backlight = i03.backlight()
    eiger: EigerDetector = i03.eiger()
    aperture_scatterguard: ApertureScatterguard = i03.aperture_scatterguard()
    detector_motion: DetectorMotion = i03.detector_motion()

    eiger.set_detector_parameters(parameters.artemis_params.detector_params)

    oav_params = OAVParameters("xrayCentring", **oav_param_files)
    experiment_params: GridScanWithEdgeDetectParams = parameters.experiment_params

    return detect_grid_and_do_gridscan(
        parameters,
        backlight,
        eiger,
        aperture_scatterguard,
        detector_motion,
        oav_params,
        experiment_params,
    )
