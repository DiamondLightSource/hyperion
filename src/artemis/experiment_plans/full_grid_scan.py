from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from bluesky import plan_stubs as bps
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import Det
from dodal.devices.oav.oav_parameters import OAVParameters

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
    from artemis.parameters.internal_parameters import InternalParameters

detector_motion: Det = None
backlight: Backlight = None
aperture_scatterguard: ApertureScatterguard = None


def create_devices():
    fgs_create_devices()
    oav_create_devices()
    from artemis.experiment_plans.fast_grid_scan_plan import fast_grid_scan_composite

    global detector_motion, backlight, aperture_scatterguard
    detector_motion = Det("BL03I", name="detector_motion")
    backlight = Backlight("BL03I-EA-BL-01:", name="backlight")
    aperture_scatterguard = fast_grid_scan_composite.aperture_scatterguard
    detector_motion.wait_for_connection()
    backlight.wait_for_connection()
    aperture_scatterguard.wait_for_connection()


def wait_for_det_to_finish_moving(detector: Det, timeout=2):
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
    raise Exception("Detector not finished moving")


def get_plan(
    parameters: InternalParameters,
    subscriptions: FGSCallbackCollection,
) -> Callable:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    gda_snap_1 = parameters.artemis_params.ispyb_params.xtal_snapshots_omega_start[0]
    gda_snap_2 = parameters.artemis_params.ispyb_params.xtal_snapshots_omega_end[0]

    snapshot_dir = os.path.dirname(os.path.abspath(gda_snap_1))
    snap_1_filename = os.path.basename(os.path.abspath(gda_snap_1))
    snap_2_filename = os.path.basename(os.path.abspath(gda_snap_2))

    zoom_params_file = "/dls_sw/i03/software/gda_versions/gda_9_27/workspace_git/gda-mx.git/configurations/i03-config/xml/jCameraManZoomLevels.xml"
    oav_json = "/dls_sw/i03/software/gda_versions/gda_9_27/workspace_git/gda-mx.git/configurations/i03-config/etc/OAVCentring.json"
    display_config = "/dls_sw/i03/software/gda_versions/var/display.configuration"
    oav_params = OAVParameters(
        oav_json,
        zoom_params_file,
        display_config,
        snapshot_dir,
        snap_1_filename,
        snap_2_filename,
        "xrayCentring",
    )

    LOGGER.info(
        f"microns_per_pixel: GDA: {parameters.artemis_params.ispyb_params.pixels_per_micron_x, parameters.artemis_params.ispyb_params.pixels_per_micron_y} Artemis {oav_params.micronsPerXPixel, oav_params.micronsPerYPixel}"
    )

    def my_plan():
        try:
            yield from grid_detection_plan(
                oav_params, None, parameters.experiment_params
            )
        except Exception as e:
            LOGGER.error(e, exc_info=True)

        yield from bps.abs_set(backlight.pos, Backlight.OUT)
        yield from bps.abs_set(
            aperture_scatterguard, aperture_scatterguard.aperture_positions.SMALL
        )
        yield from wait_for_det_to_finish_moving(detector_motion)

        yield from fgs_get_plan(parameters, subscriptions)

    return my_plan()
