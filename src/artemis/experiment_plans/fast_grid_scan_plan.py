from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Callable

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.utils import ProgressBarManager
from dodal import i03
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.eiger import DetectorParams
from dodal.devices.fast_grid_scan import set_fast_grid_scan_params
from dodal.i03 import (
    DCM,
    OAV,
    ApertureScatterguard,
    Backlight,
    EigerDetector,
    FastGridScan,
    S4SlitGaps,
    Smargon,
    Synchrotron,
    Undulator,
    Zebra,
)

import artemis.log
from artemis.device_setup_plans.setup_zebra_for_fgs import (
    set_zebra_shutter_to_manual,
    setup_zebra_for_fgs,
)
from artemis.exceptions import WarningException
from artemis.parameters.beamline_parameters import (
    GDABeamlineParameters,
    get_beamline_prefixes,
)
from artemis.parameters.constants import (
    I03_BEAMLINE_PARAMETER_PATH,
    ISPYB_PLAN_NAME,
    SIM_BEAMLINE,
)
from artemis.tracing import TRACER
from artemis.utils import Point3D

if TYPE_CHECKING:
    from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
        FGSCallbackCollection,
    )
    from artemis.parameters.internal_parameters import InternalParameters


class FGSComposite:
    """A device consisting of all the Devices required for a fast gridscan."""

    dcm: DCM
    oav: OAV
    aperture_scatterguard: ApertureScatterguard
    backlight: Backlight
    eiger: EigerDetector
    fast_grid_scan: FastGridScan
    s4_slit_gaps: S4SlitGaps
    sample_motors: Smargon
    synchrotron: Synchrotron
    undulator: Undulator
    zebra: Zebra

    def __init__(
        self,
        aperture_positions: AperturePositions = None,
        detector_params: DetectorParams = None,
        fake: bool = False,
    ):
        self.dcm = i03.dcm(fake_with_ophyd_sim=fake)
        self.oav = i03.oav(fake_with_ophyd_sim=fake)
        self.aperture_scatterguard = i03.aperture_scatterguard(
            fake_with_ophyd_sim=fake, aperture_positions=aperture_positions
        )
        self.backlight = i03.backlight(fake_with_ophyd_sim=fake)
        self.eiger = i03.eiger(
            wait_for_connection=False, fake_with_ophyd_sim=fake, params=detector_params
        )
        self.fast_grid_scan = i03.fast_grid_scan(fake_with_ophyd_sim=fake)
        self.s4_slit_gaps = i03.s4_slit_gaps(fake_with_ophyd_sim=fake)
        self.sample_motors = i03.smargon(fake_with_ophyd_sim=fake)
        self.undulator = i03.undulator(fake_with_ophyd_sim=fake)
        self.synchrotron = i03.synchrotron(fake_with_ophyd_sim=fake)
        self.zebra = i03.zebra(fake_with_ophyd_sim=fake)


fast_grid_scan_composite: FGSComposite | None = None


def get_beamline_parameters():
    return GDABeamlineParameters.from_file(I03_BEAMLINE_PARAMETER_PATH)


def create_devices():
    """Creates the devices required for the plan and connect to them"""
    global fast_grid_scan_composite
    prefixes = get_beamline_prefixes()
    artemis.log.LOGGER.info(
        f"Creating devices for {prefixes.beamline_prefix} and {prefixes.insertion_prefix}"
    )
    aperture_positions = AperturePositions.from_gda_beamline_params(
        get_beamline_parameters()
    )
    artemis.log.LOGGER.info("Connecting to EPICS devices...")
    fast_grid_scan_composite = FGSComposite(aperture_positions=aperture_positions)
    artemis.log.LOGGER.info("Connected.")


def set_aperture_for_bbox_size(
    aperture_device: ApertureScatterguard,
    bbox_size: list[int],
):
    # bbox_size is [x,y,z], for i03 we only care about x
    if bbox_size[0] <= 1:
        aperture_size_positions = aperture_device.aperture_positions.SMALL
    elif 1 < bbox_size[0] < 3:
        aperture_size_positions = aperture_device.aperture_positions.MEDIUM
    else:
        aperture_size_positions = aperture_device.aperture_positions.LARGE
    artemis.log.LOGGER.info(
        f"Setting aperture to {aperture_size_positions} based on bounding box size {bbox_size}."
    )
    yield from bps.abs_set(aperture_device, aperture_size_positions)


def read_hardware_for_ispyb(
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
):
    artemis.log.LOGGER.info(
        "Reading status of beamline parameters for ispyb deposition."
    )
    yield from bps.create(
        name=ISPYB_PLAN_NAME
    )  # gives name to event *descriptor* document
    yield from bps.read(undulator.gap)
    yield from bps.read(synchrotron.machine_status.synchrotron_mode)
    yield from bps.read(s4_slit_gaps.xgap)
    yield from bps.read(s4_slit_gaps.ygap)
    yield from bps.save()


@bpp.set_run_key_decorator("move_xyz")
@bpp.run_decorator(md={"subplan_name": "move_xyz"})
def move_xyz(
    sample_motors,
    xray_centre_motor_position: Point3D,
    md={
        "plan_name": "move_xyz",
    },
):
    """Move 'sample motors' to a specific motor position (e.g. a position obtained
    from gridscan processing results)"""
    artemis.log.LOGGER.info(f"Moving Smargon x, y, z to: {xray_centre_motor_position}")
    yield from bps.mv(
        sample_motors.x,
        xray_centre_motor_position.x,
        sample_motors.y,
        xray_centre_motor_position.y,
        sample_motors.z,
        xray_centre_motor_position.z,
    )


def wait_for_fgs_valid(fgs_motors: FastGridScan, timeout=0.5):
    artemis.log.LOGGER.info("Waiting for valid fgs_params")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        scan_invalid = yield from bps.rd(fgs_motors.scan_invalid)
        pos_counter = yield from bps.rd(fgs_motors.position_counter)
        artemis.log.LOGGER.debug(
            f"Scan invalid: {scan_invalid} and position counter: {pos_counter}"
        )
        if not scan_invalid and pos_counter == 0:
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise WarningException("Scan invalid - pin too long/short/bent and out of range")


def tidy_up_plans(fgs_composite: FGSComposite):
    artemis.log.LOGGER.info("Tidying up Zebra")
    yield from set_zebra_shutter_to_manual(fgs_composite.zebra)


@bpp.set_run_key_decorator("run_gridscan")
@bpp.run_decorator(md={"subplan_name": "run_gridscan"})
def run_gridscan(
    fgs_composite: FGSComposite,
    parameters: InternalParameters,
    md={
        "plan_name": "run_gridscan",
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
        yield from read_hardware_for_ispyb(
            fgs_composite.undulator,
            fgs_composite.synchrotron,
            fgs_composite.s4_slit_gaps,
        )

    fgs_motors = fgs_composite.fast_grid_scan

    # TODO: Check topup gate
    yield from set_fast_grid_scan_params(fgs_motors, parameters.experiment_params)
    yield from wait_for_fgs_valid(fgs_motors)

    @bpp.set_run_key_decorator("do_fgs")
    @bpp.run_decorator(md={"subplan_name": "do_fgs"})
    @bpp.stage_decorator([fgs_composite.eiger])
    def do_fgs():
        yield from bps.wait()  # Wait for all moves to complete
        yield from bps.kickoff(fgs_motors)
        yield from bps.complete(fgs_motors, wait=True)

    with TRACER.start_span("do_fgs"):
        yield from do_fgs()

    with TRACER.start_span("move_to_z_0"):
        yield from bps.abs_set(fgs_motors.z_steps, 0, wait=False)


@bpp.set_run_key_decorator("run_gridscan_and_move")
@bpp.run_decorator(md={"subplan_name": "run_gridscan_and_move"})
def run_gridscan_and_move(
    fgs_composite: FGSComposite,
    parameters: InternalParameters,
    subscriptions: FGSCallbackCollection,
):
    """A multi-run plan which runs a gridscan, gets the results from zocalo
    and moves to the centre of mass determined by zocalo"""

    # We get the initial motor positions so we can return to them on zocalo failure
    initial_xyz = Point3D(
        (yield from bps.rd(fgs_composite.sample_motors.x)),
        (yield from bps.rd(fgs_composite.sample_motors.y)),
        (yield from bps.rd(fgs_composite.sample_motors.z)),
    )

    yield from setup_zebra_for_fgs(fgs_composite.zebra)

    # While the gridscan is happening we want to write out nexus files and trigger zocalo
    @bpp.subs_decorator([subscriptions.nexus_handler, subscriptions.zocalo_handler])
    def gridscan_with_subscriptions(fgs_composite, params):
        artemis.log.LOGGER.info("Starting grid scan")
        yield from run_gridscan(fgs_composite, params)

    yield from gridscan_with_subscriptions(fgs_composite, parameters)

    # the data were submitted to zocalo by the zocalo callback during the gridscan,
    # but results may not be ready, and need to be collected regardless.
    # it might not be ideal to block for this, see #327
    xray_centre, bbox_size = subscriptions.zocalo_handler.wait_for_results(initial_xyz)

    if bbox_size is not None:
        with TRACER.start_span("change_aperture"):
            yield from set_aperture_for_bbox_size(
                fgs_composite.aperture_scatterguard, bbox_size
            )

    # once we have the results, go to the appropriate position
    artemis.log.LOGGER.info("Moving to centre of mass.")
    with TRACER.start_span("move_to_result"):
        yield from move_xyz(
            fgs_composite.sample_motors,
            xray_centre,
        )


def get_plan(
    parameters: InternalParameters,
    subscriptions: FGSCallbackCollection,
) -> Callable:
    """Create the plan to run the grid scan based on provided parameters.

    The ispyb handler should be added to the whole gridscan as we want to capture errors
    at any point in it.

    Args:
        parameters (InternalParameters): The parameters to run the scan.

    Returns:
        Generator: The plan for the gridscan
    """
    assert fast_grid_scan_composite is not None
    fast_grid_scan_composite.eiger.set_detector_parameters(
        parameters.artemis_params.detector_params
    )

    @bpp.finalize_decorator(lambda: tidy_up_plans(fast_grid_scan_composite))
    @bpp.subs_decorator(subscriptions.ispyb_handler)
    def run_gridscan_and_move_and_tidy(fgs_composite, params, comms):
        yield from run_gridscan_and_move(fgs_composite, params, comms)

    return run_gridscan_and_move_and_tidy(
        fast_grid_scan_composite, parameters, subscriptions
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--beamline",
        help="The beamline prefix this is being run on",
        default=SIM_BEAMLINE,
    )
    args = parser.parse_args()

    RE = RunEngine({})
    RE.waiting_hook = ProgressBarManager()

    parameters = InternalParameters(beamline=args.artemis_parameters.beamline)
    subscriptions = FGSCallbackCollection.from_params(parameters)

    create_devices()

    RE(get_plan(parameters, subscriptions))
