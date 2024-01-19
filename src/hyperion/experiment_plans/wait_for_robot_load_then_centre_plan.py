from __future__ import annotations

import dataclasses
import json

import bluesky.plan_stubs as bps
from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.aperturescatterguard import ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.DCM import DCM
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.flux import Flux
from dodal.devices.focusing_mirror import FocusingMirror, VFMMirrorVoltages
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.panda_fast_grid_scan import PandAFastGridScan
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
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
    set_energy_plan,
)
from hyperion.log import LOGGER
from hyperion.parameters.plan_specific.pin_centre_then_xray_centre_params import (
    PinCentreThenXrayCentreInternalParameters,
)
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
)


@dataclasses.dataclass
class WaitForRobotLoadThenCentreComposite:
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


def create_devices(context: BlueskyContext) -> WaitForRobotLoadThenCentreComposite:
    from hyperion.utils.context import device_composite_from_context

    return device_composite_from_context(context, WaitForRobotLoadThenCentreComposite)


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


def wait_for_robot_load_then_centre_plan(
    composite: WaitForRobotLoadThenCentreComposite,
    parameters: WaitForRobotLoadThenCentreInternalParameters,
):
    set_energy_composite = SetEnergyComposite(
        vfm=composite.vfm,
        vfm_mirror_voltages=composite.vfm_mirror_voltages,
        dcm=composite.dcm,
        undulator_dcm=composite.undulator_dcm,
        xbpm_feedback=composite.xbpm_feedback,
        attenuator=composite.attenuator,
    )

    if parameters.experiment_params.requested_energy_kev:
        yield from set_energy_plan(
            parameters.experiment_params.requested_energy_kev,
            set_energy_composite,
        )

    yield from wait_for_smargon_not_disabled(composite.smargon)

    params_json = json.loads(parameters.json())
    pin_centre_params = PinCentreThenXrayCentreInternalParameters(**params_json)

    grid_detect_then_xray_centre_composite = GridDetectThenXRayCentreComposite(
        aperture_scatterguard=composite.aperture_scatterguard,
        attenuator=composite.attenuator,
        backlight=composite.backlight,
        detector_motion=composite.detector_motion,
        eiger=composite.eiger,
        fast_grid_scan=composite.fast_grid_scan,
        flux=composite.flux,
        oav=composite.oav,
        pin_tip_detection=composite.pin_tip_detection,
        smargon=composite.smargon,
        synchrotron=composite.synchrotron,
        s4_slit_gaps=composite.s4_slit_gaps,
        undulator=composite.undulator,
        xbpm_feedback=composite.xbpm_feedback,
        zebra=composite.zebra,
        zocalo=composite.zocalo,
        panda=composite.panda,
        panda_fast_grid_scan=composite.panda_fast_grid_scan,
    )
    yield from pin_centre_then_xray_centre_plan(
        grid_detect_then_xray_centre_composite, pin_centre_params
    )


def wait_for_robot_load_then_centre(
    composite: WaitForRobotLoadThenCentreComposite,
    parameters: WaitForRobotLoadThenCentreInternalParameters,
) -> MsgGenerator:
    eiger: EigerDetector = composite.eiger

    actual_energy_ev = 1000 * (yield from bps.rd(composite.dcm.energy_in_kev))
    parameters.hyperion_params.ispyb_params.current_energy_ev = actual_energy_ev
    if not parameters.experiment_params.requested_energy_kev:
        parameters.hyperion_params.detector_params.expected_energy_ev = actual_energy_ev

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    yield from start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.experiment_params.detector_distance,
        wait_for_robot_load_then_centre_plan(composite, parameters),
    )
