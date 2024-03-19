from __future__ import annotations

import dataclasses
import json
from typing import cast

import bluesky.plan_stubs as bps
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.DCM import DCM
from dodal.devices.detector.det_resolution import resolution
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.flux import Flux
from dodal.devices.focusing_mirror import FocusingMirror, VFMMirrorVoltages
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.panda_fast_grid_scan import PandAFastGridScan
from dodal.devices.robot import BartRobot, SampleLocation
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon, StubPosition
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.undulator_dcm import UndulatorDCM
from dodal.devices.xbpm_feedback import XBPMFeedback
from dodal.devices.zebra import Zebra
from dodal.devices.zocalo import ZocaloResults
from ophyd_async.panda import PandA

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
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.parameters.plan_specific.robot_load_then_center_params import (
    RobotLoadThenCentreInternalParameters,
)
from hyperion.utils.utils import convert_eV_to_angstrom


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
    fast_grid_scan: FastGridScan
    flux: Flux
    oav: OAV
    pin_tip_detection: PinTipDetection
    smargon: Smargon
    synchrotron: Synchrotron
    s4_slit_gaps: S4SlitGaps
    undulator: Undulator
    zebra: Zebra
    zocalo: ZocaloResults
    panda: PandA
    panda_fast_grid_scan: PandAFastGridScan

    # SetEnergyComposite fields
    vfm: FocusingMirror
    vfm_mirror_voltages: VFMMirrorVoltages
    dcm: DCM
    undulator_dcm: UndulatorDCM

    # RobotLoad fields
    robot: BartRobot


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


def prepare_for_robot_load(composite: RobotLoadThenCentreComposite):
    yield from bps.abs_set(
        composite.aperture_scatterguard,
        AperturePositions.ROBOT_LOAD,
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


def robot_load_then_centre_plan(
    composite: RobotLoadThenCentreComposite,
    parameters: RobotLoadThenCentreInternalParameters,
):
    yield from prepare_for_robot_load(composite)

    yield from bps.abs_set(
        composite.robot,
        SampleLocation(
            parameters.experiment_params.sample_puck,
            parameters.experiment_params.sample_pin,
        ),
        group="robot_load",
    )

    if parameters.experiment_params.requested_energy_kev:
        yield from set_energy_plan(
            parameters.experiment_params.requested_energy_kev,
            cast(SetEnergyComposite, composite),
        )

    yield from bps.wait("robot_load")

    yield from wait_for_smargon_not_disabled(composite.smargon)

    params_json = json.loads(parameters.json())
    pin_centre_params = PinCentreThenXrayCentreInternalParameters(**params_json)

    yield from pin_centre_then_xray_centre_plan(
        cast(GridDetectThenXRayCentreComposite, composite), pin_centre_params
    )


def robot_load_then_centre(
    composite: RobotLoadThenCentreComposite,
    parameters: RobotLoadThenCentreInternalParameters,
) -> MsgGenerator:
    eiger: EigerDetector = composite.eiger

    actual_energy_ev = 1000 * (
        yield from read_energy(cast(SetEnergyComposite, composite))
    )

    parameters.hyperion_params.ispyb_params.current_energy_ev = actual_energy_ev
    if not parameters.experiment_params.requested_energy_kev:
        parameters.hyperion_params.detector_params.expected_energy_ev = actual_energy_ev
    else:
        parameters.hyperion_params.detector_params.expected_energy_ev = (
            parameters.experiment_params.requested_energy_kev * 1000
        )

    wavelength_angstroms = convert_eV_to_angstrom(actual_energy_ev)
    parameters.hyperion_params.ispyb_params.resolution = resolution(
        parameters.hyperion_params.detector_params,
        wavelength_angstroms,
        parameters.experiment_params.detector_distance,
    )

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    yield from start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.experiment_params.detector_distance,
        robot_load_then_centre_plan(composite, parameters),
    )
