from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path
from typing import cast

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import AperturePosition, ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import PandAFastGridScan, ZebraFastGridScan
from dodal.devices.flux import Flux
from dodal.devices.focusing_mirror import FocusingMirrorWithStripes, VFMMirrorVoltages
from dodal.devices.motors import XYZPositioner
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.robot import BartRobot, SampleLocation
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon, StubPosition
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.thawer import Thawer
from dodal.devices.undulator import Undulator
from dodal.devices.undulator_dcm import UndulatorDCM
from dodal.devices.webcam import Webcam
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zocalo import ZocaloResults
from dodal.plans.motor_util_plans import MoveTooLarge, home_and_reset_wrapper
from ophyd_async.panda import HDFPanda

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
)
from hyperion.experiment_plans.pin_centre_then_xray_centre_plan import (
    pin_centre_then_xray_centre_plan,
)
from hyperion.experiment_plans.set_energy_plan import (
    SetEnergyComposite,
    read_energy,
    set_energy_plan,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import RobotLoadThenCentre


@dataclasses.dataclass
class RobotLoadThenCentreComposite:
    # common fields
    xbpm_feedback: XBPMFeedback
    attenuator: Attenuator

    # GridDetectThenXRayCentreComposite fields
    aperture_scatterguard: ApertureScatterguard
    backlight: Backlight
    detector_motion: DetectorMotion
    eiger: EigerDetector
    zebra_fast_grid_scan: ZebraFastGridScan
    flux: Flux
    oav: OAV
    pin_tip_detection: PinTipDetection
    smargon: Smargon
    synchrotron: Synchrotron
    s4_slit_gaps: S4SlitGaps
    undulator: Undulator
    zebra: Zebra
    zocalo: ZocaloResults
    panda: HDFPanda
    panda_fast_grid_scan: PandAFastGridScan
    thawer: Thawer

    # SetEnergyComposite fields
    vfm: FocusingMirrorWithStripes
    vfm_mirror_voltages: VFMMirrorVoltages
    dcm: DCM
    undulator_dcm: UndulatorDCM

    # RobotLoad fields
    robot: BartRobot
    webcam: Webcam
    lower_gonio: XYZPositioner


def create_devices(context: BlueskyContext) -> RobotLoadThenCentreComposite:
    from hyperion.utils.context import device_composite_from_context

    return device_composite_from_context(context, RobotLoadThenCentreComposite)


def wait_for_smargon_not_disabled(smargon: Smargon, timeout=60):
    """Waits for the smargon disabled flag to go low. The robot hardware is responsible
    for setting this to low when it is safe to move. It does this through a physical
    connection between the robot and the smargon.
    """
    LOGGER.info("Waiting for smargon enabled")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        smargon_disabled = yield from bps.rd(smargon.disabled)
        if not smargon_disabled:
            LOGGER.info("Smargon now enabled")
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise TimeoutError(
        "Timed out waiting for smargon to become enabled after robot load"
    )


def take_robot_snapshots(oav: OAV, webcam: Webcam, directory: Path):
    time_now = datetime.now()
    snapshot_format = f"{time_now.strftime('%H%M%S')}_{{device}}_after_load"
    for device in [oav.snapshot, webcam]:
        yield from bps.abs_set(
            device.filename, snapshot_format.format(device=device.name)
        )
        yield from bps.abs_set(device.directory, str(directory))
        yield from bps.trigger(device, group="snapshots")
    yield from bps.wait("snapshots")


def prepare_for_robot_load(composite: RobotLoadThenCentreComposite):
    yield from bps.abs_set(
        composite.aperture_scatterguard,
        AperturePosition.ROBOT_LOAD,
        group="prepare_robot_load",
    )

    yield from bps.mv(composite.smargon.stub_offsets, StubPosition.RESET_TO_ROBOT_LOAD)

    # fmt: off
    yield from bps.mv(composite.smargon.x, 0,
                      composite.smargon.y, 0,
                      composite.smargon.z, 0,
                      composite.smargon.omega, 0,
                      composite.smargon.chi, 0,
                      composite.smargon.phi, 0)
    # fmt: on

    yield from bps.wait("prepare_robot_load")


def do_robot_load(
    composite: RobotLoadThenCentreComposite,
    sample_location: SampleLocation,
    demand_energy_ev: float | None,
    thawing_time: float,
):
    yield from bps.abs_set(
        composite.robot,
        sample_location,
        group="robot_load",
    )

    if demand_energy_ev:
        yield from set_energy_plan(
            demand_energy_ev / 1000,
            cast(SetEnergyComposite, composite),
        )

    yield from bps.wait("robot_load")

    yield from bps.abs_set(
        composite.thawer.thaw_for_time_s, thawing_time, group="thawing_finished"
    )
    yield from wait_for_smargon_not_disabled(composite.smargon)


def raise_exception_if_moved_out_of_cryojet(exception):
    yield from bps.null()
    if isinstance(exception, MoveTooLarge):
        raise Exception(
            f"Moving {exception.axis} back to {exception.position} after \
                        robot load would move it out of the cryojet. The max safe \
                        distance is {exception.maximum_move}"
        )


def robot_load_then_centre_plan(
    composite: RobotLoadThenCentreComposite,
    params: RobotLoadThenCentre,
):
    yield from prepare_for_robot_load(composite)

    @bpp.run_decorator(
        md={
            "subplan_name": CONST.PLAN.ROBOT_LOAD,
            "metadata": {
                "visit_path": params.ispyb_params.visit_path,
                "sample_id": params.sample_id,
                "sample_puck": params.sample_puck,
                "sample_pin": params.sample_pin,
            },
            "activate_callbacks": [
                "RobotLoadISPyBCallback",
            ],
        }
    )
    def robot_load_and_snapshots():
        # TODO: get these from one source of truth #1347
        assert params.sample_puck is not None
        assert params.sample_pin is not None

        robot_load_plan = do_robot_load(
            composite,
            SampleLocation(params.sample_puck, params.sample_pin),
            params.demand_energy_ev,
            params.thawing_time,
        )

        # The lower gonio must be in the correct position for the robot load and we
        # want to put it back afterwards. Note we don't wait the robot is interlocked
        # to the lower gonio and the  move is quicker than the robot takes to get to the
        # load position.
        yield from bpp.contingency_wrapper(
            home_and_reset_wrapper(
                robot_load_plan,
                composite.lower_gonio,
                BartRobot.LOAD_TOLERANCE_MM,
                CONST.HARDWARE.CRYOJET_MARGIN_MM,
                "lower_gonio",
                wait_for_all=False,
            ),
            except_plan=raise_exception_if_moved_out_of_cryojet,
        )

        yield from take_robot_snapshots(
            composite.oav, composite.webcam, params.snapshot_directory
        )

        yield from bps.create(name=CONST.DESCRIPTORS.ROBOT_LOAD)
        yield from bps.read(composite.robot.barcode)
        yield from bps.read(composite.oav.snapshot)
        yield from bps.read(composite.webcam)
        yield from bps.save()

        yield from bps.wait("reset-lower_gonio")

    yield from robot_load_and_snapshots()

    yield from pin_centre_then_xray_centre_plan(
        cast(GridDetectThenXRayCentreComposite, composite),
        params.pin_centre_then_xray_centre_params(),
    )


def robot_load_then_centre(
    composite: RobotLoadThenCentreComposite,
    parameters: RobotLoadThenCentre,
) -> MsgGenerator:
    eiger: EigerDetector = composite.eiger

    detector_params = parameters.detector_params
    if not detector_params.expected_energy_ev:
        actual_energy_ev = 1000 * (
            yield from read_energy(cast(SetEnergyComposite, composite))
        )
        detector_params.expected_energy_ev = actual_energy_ev
    eiger.set_detector_parameters(detector_params)

    yield from start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.detector_distance_mm,
        robot_load_then_centre_plan(composite, parameters),
        group=CONST.WAIT.GRID_READY_FOR_DC,
    )
