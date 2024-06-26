from __future__ import annotations

from pathlib import Path

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.fast_grid_scan import (
    set_fast_grid_scan_params as set_flyscan_params,
)
from dodal.devices.smargon import StubPosition
from dodal.devices.zocalo import (
    get_processing_result,
)
from dodal.devices.zocalo.zocalo_results import (
    ZOCALO_READING_PLAN_NAME,
    ZOCALO_STAGE_GROUP,
)

from hyperion.device_setup_plans.manipulate_sample import move_x_y_z
from hyperion.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_ispyb_during_collection,
    read_hardware_for_ispyb_pre_collection,
    read_hardware_for_nexus_writer,
)
from hyperion.device_setup_plans.setup_panda import (
    disarm_panda_for_gridscan,
    set_and_create_panda_directory,
    setup_panda_for_flyscan,
)
from hyperion.device_setup_plans.setup_zebra import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_panda_flyscan,
)
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_decorator,
)
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    kickoff_and_complete_gridscan,
    set_aperture_for_bbox_size,
    wait_for_gridscan_valid,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan
from hyperion.tracing import TRACER
from hyperion.utils.context import device_composite_from_context

PANDA_SETUP_PATH = (
    "/dls_sw/i03/software/daq_configuration/panda_configs/flyscan_pcap_ignore_seq.yaml"
)


class SmargonSpeedException(Exception):
    pass


def create_devices(context: BlueskyContext) -> FlyScanXRayCentreComposite:
    """Creates the devices required for the plan and connect to them"""
    return device_composite_from_context(context, FlyScanXRayCentreComposite)


def tidy_up_plans(fgs_composite: FlyScanXRayCentreComposite):
    LOGGER.info("Disabling panda blocks")
    yield from disarm_panda_for_gridscan(
        fgs_composite.panda, group="panda_flyscan_tidy"
    )
    LOGGER.info("Tidying up Zebra")
    yield from set_zebra_shutter_to_manual(
        fgs_composite.zebra, group="panda_flyscan_tidy", wait=True
    )

    yield from bps.wait(group="panda_flyscan_tidy", timeout=10)


@bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_MAIN)
@bpp.run_decorator(md={"subplan_name": CONST.PLAN.GRIDSCAN_MAIN})
def run_gridscan(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
    md={
        "plan_name": "run_panda_gridscan",
    },
):
    sample_motors = fgs_composite.sample_motors

    # Currently gridscan only works for omega 0, see #
    with TRACER.start_span("moving_omega_to_0"):
        yield from bps.abs_set(sample_motors.omega, 0)

    # We only subscribe to the communicator callback for run_gridscan, so this is where
    # we should generate an event reading the values which need to be included in the
    # ispyb deposition
    with TRACER.start_span("ispyb_hardware_readings"):
        yield from read_hardware_for_ispyb_pre_collection(
            fgs_composite.undulator,
            fgs_composite.synchrotron,
            fgs_composite.s4_slit_gaps,
            fgs_composite.aperture_scatterguard,
            fgs_composite.robot,
            fgs_composite.smargon,
        )
        yield from read_hardware_for_ispyb_during_collection(
            fgs_composite.attenuator, fgs_composite.flux, fgs_composite.dcm
        )

    fgs_motors = fgs_composite.panda_fast_grid_scan

    LOGGER.info("Setting fgs params")
    yield from set_flyscan_params(fgs_motors, parameters.panda_FGS_params)

    yield from wait_for_gridscan_valid(fgs_motors)

    LOGGER.info("Waiting for arming to finish")
    yield from bps.wait("ready_for_data_collection")
    yield from bps.stage(fgs_composite.eiger)

    # This needs to occur after eiger is armed so that
    # the HDF5 meta file is present for nexgen to inspect
    with TRACER.start_span("nexus_hardware_readings"):
        yield from read_hardware_for_nexus_writer(fgs_composite.eiger)

    yield from kickoff_and_complete_gridscan(
        fgs_motors,
        fgs_composite.eiger,
        fgs_composite.synchrotron,
        parameters.zocalo_environment,
        [parameters.scan_points_first_grid, parameters.scan_points_second_grid],
        parameters.scan_indices,
    )

    yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


@bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_AND_MOVE)
@bpp.run_decorator(md={"subplan_name": CONST.PLAN.GRIDSCAN_AND_MOVE})
def run_gridscan_and_move(
    fgs_composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
):
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""

    # We get the initial motor positions so we can return to them on zocalo failure
    initial_xyz = np.array(
        [
            (yield from bps.rd(fgs_composite.sample_motors.x)),
            (yield from bps.rd(fgs_composite.sample_motors.y)),
            (yield from bps.rd(fgs_composite.sample_motors.z)),
        ]
    )

    LOGGER.info("Setting up Panda for flyscan")

    run_up_distance_mm = yield from bps.rd(
        fgs_composite.panda_fast_grid_scan.run_up_distance_mm
    )

    # Set the time between x steps pv
    DEADTIME_S = 1e-6  # according to https://www.dectris.com/en/detectors/x-ray-detectors/eiger2/eiger2-for-synchrotrons/eiger2-x/

    time_between_x_steps_ms = (DEADTIME_S + parameters.exposure_time_s) * 1e3

    smargon_speed_limit_mm_per_s = yield from bps.rd(
        fgs_composite.smargon.x.max_velocity
    )

    sample_velocity_mm_per_s = (
        parameters.panda_FGS_params.x_step_size * 1e3 / time_between_x_steps_ms
    )
    if sample_velocity_mm_per_s > smargon_speed_limit_mm_per_s:
        raise SmargonSpeedException(
            f"Smargon speed was calculated from x step size\
            {parameters.panda_FGS_params.x_step_size} and\
            time_between_x_steps_ms {time_between_x_steps_ms} as\
            {sample_velocity_mm_per_s}. The smargon's speed limit is\
            {smargon_speed_limit_mm_per_s} mm/s."
        )
    else:
        LOGGER.info(
            f"Panda grid scan: Smargon speed set to {smargon_speed_limit_mm_per_s} mm/s and using a run-up distance of {run_up_distance_mm}"
        )

    yield from bps.mv(
        fgs_composite.panda_fast_grid_scan.time_between_x_steps_ms,
        time_between_x_steps_ms,
    )

    panda_directory = Path(parameters.storage_directory, "panda")

    set_and_create_panda_directory(panda_directory)

    yield from setup_panda_for_flyscan(
        fgs_composite.panda,
        PANDA_SETUP_PATH,
        parameters.panda_FGS_params,
        initial_xyz[0],
        parameters.exposure_time_s,
        time_between_x_steps_ms,
        sample_velocity_mm_per_s,
    )

    LOGGER.info("Setting up Zebra for panda flyscan")
    yield from setup_zebra_for_panda_flyscan(fgs_composite.zebra, wait=True)

    LOGGER.info("Starting grid scan")
    yield from bps.stage(
        fgs_composite.zocalo, group=ZOCALO_STAGE_GROUP
    )  # connect to zocalo and make sure the queue is clear
    yield from run_gridscan(fgs_composite, parameters)

    LOGGER.info("Grid scan finished, getting results.")

    with TRACER.start_span("wait_for_zocalo"):
        yield from bps.trigger_and_read(
            [fgs_composite.zocalo], name=ZOCALO_READING_PLAN_NAME
        )
        LOGGER.info("Zocalo triggered and read, interpreting results.")
        xray_centre, bbox_size = yield from get_processing_result(fgs_composite.zocalo)
        LOGGER.info(f"Got xray centre: {xray_centre}, bbox size: {bbox_size}")
        if xray_centre is not None:
            xray_centre = parameters.panda_FGS_params.grid_position_to_motor_position(
                xray_centre
            )
        else:
            xray_centre = initial_xyz
            LOGGER.warning("No X-ray centre recieved")
        if bbox_size is not None:
            with TRACER.start_span("change_aperture"):
                yield from set_aperture_for_bbox_size(
                    fgs_composite.aperture_scatterguard, bbox_size
                )
        else:
            LOGGER.warning("No bounding box size recieved")

    # once we have the results, go to the appropriate position
    LOGGER.info("Moving to centre of mass.")
    with TRACER.start_span("move_to_result"):
        yield from move_x_y_z(fgs_composite.sample_motors, *xray_centre, wait=True)

    if parameters.panda_FGS_params.set_stub_offsets:
        LOGGER.info("Recentring smargon co-ordinate system to this point.")
        yield from bps.mv(
            fgs_composite.sample_motors.stub_offsets, StubPosition.CURRENT_AS_CENTER
        )

    # Turn off dev/shm streaming to avoid filling disk, see https://github.com/DiamondLightSource/hyperion/issues/1395
    LOGGER.info("Turning off Eiger dev/shm streaming")
    yield from bps.abs_set(fgs_composite.eiger.odin.fan.dev_shm_enable, 0)

    # Wait on everything before returning to GDA (particularly apertures), can be removed
    # when we do not return to GDA here
    yield from bps.wait()


def panda_flyscan_xray_centre(
    composite: FlyScanXRayCentreComposite,
    parameters: ThreeDGridScan,
) -> MsgGenerator:
    """Create the plan to run the grid scan based on provided parameters.

    The ispyb handler should be added to the whole gridscan as we want to capture errors
    at any point in it.

    Args:
        parameters (ThreeDGridScan): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """

    composite.eiger.set_detector_parameters(parameters.detector_params)
    composite.zocalo.zocalo_environment = parameters.zocalo_environment
    parameters.features.update_self_from_server()

    @bpp.set_run_key_decorator(CONST.PLAN.GRIDSCAN_OUTER)
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": CONST.PLAN.GRIDSCAN_OUTER,
            CONST.TRIGGER.ZOCALO: CONST.PLAN.DO_FGS,
            "hyperion_parameters": parameters.json(),
            "activate_callbacks": [
                "GridscanNexusFileCallback",
            ],
        }
    )
    @bpp.finalize_decorator(lambda: tidy_up_plans(composite))
    @transmission_and_xbpm_feedback_for_collection_decorator(
        composite.xbpm_feedback,
        composite.attenuator,
        parameters.transmission_frac,
    )
    def run_gridscan_and_move_and_tidy(fgs_composite, params):
        yield from run_gridscan_and_move(fgs_composite, params)

    return run_gridscan_and_move_and_tidy(composite, parameters)
