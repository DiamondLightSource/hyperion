from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from bluesky import plan_stubs as bps
from dodal import i03
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters

from artemis.experiment_plans.fast_grid_scan_plan import (
    create_devices as fgs_create_devices,
)
from artemis.experiment_plans.fast_grid_scan_plan import get_plan as fgs_get_plan
from artemis.experiment_plans.oav_grid_detection_plan import (
    create_devices as oav_create_devices,
)
from artemis.experiment_plans.oav_grid_detection_plan import grid_detection_plan
from artemis.log import LOGGER

if TYPE_CHECKING:
    from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
        FGSCallbackCollection,
    )
    from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
        FGSInternalParameters,
    )


def create_devices():
    fgs_create_devices()
    oav_create_devices()

    i03.detector_motion().wait_for_connection()
    i03.backlight().wait_for_connection()
    i03.aperture_scatterguard().wait_for_connection()


def wait_for_det_to_finish_moving(detector: DetectorMotion, timeout=2):
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


def get_plan(
    parameters: FGSInternalParameters,
    subscriptions: FGSCallbackCollection,
    oav_param_files: dict = OAV_CONFIG_FILE_DEFAULTS,
) -> Callable:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    backlight: Backlight = i03.backlight()
    aperture_scatterguard: ApertureScatterguard = i03.aperture_scatterguard()
    detector_motion: DetectorMotion = i03.detector_motion()

    gda_snap_1 = parameters.artemis_params.ispyb_params.xtal_snapshots_omega_start[0]
    gda_snap_2 = parameters.artemis_params.ispyb_params.xtal_snapshots_omega_end[0]

    snapshot_paths = {
        "snapshot_dir": os.path.dirname(os.path.abspath(gda_snap_1)),
        "snap_1_filename": os.path.basename(os.path.abspath(gda_snap_1)),
        "snap_2_filename": os.path.basename(os.path.abspath(gda_snap_2)),
    }

    oav_params = OAVParameters("loopCentring", **oav_param_files)

    LOGGER.info(
        f"microns_per_pixel: GDA: {parameters.artemis_params.ispyb_params.microns_per_pixel_x, parameters.artemis_params.ispyb_params.microns_per_pixel_y} Artemis {oav_params.micronsPerXPixel, oav_params.micronsPerYPixel}"
    )

    def detect_grid_and_do_gridscan():
        yield from grid_detection_plan(
            oav_params, parameters.experiment_params, snapshot_paths
        )

        yield from bps.abs_set(backlight.pos, Backlight.OUT)
        yield from bps.abs_set(
            aperture_scatterguard, aperture_scatterguard.aperture_positions.SMALL
        )
        yield from wait_for_det_to_finish_moving(detector_motion)

        yield from fgs_get_plan(parameters, subscriptions)

    return detect_grid_and_do_gridscan()
