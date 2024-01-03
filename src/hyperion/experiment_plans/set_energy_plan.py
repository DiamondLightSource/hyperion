"""Plan that comprises:
    * Disable feedback
    * Set undulator energy to the requested amount
    * Adjust DCM and mirrors for the new energy
    * reenable feedback
"""
import dataclasses

from bluesky import plan_stubs as bps
from dodal.devices.attenuator import Attenuator
from dodal.devices.DCM import DCM
from dodal.devices.focusing_mirror import FocusingMirror, VFMMirrorVoltages
from dodal.devices.undulator_dcm import UndulatorDCM
from dodal.devices.xbpm_feedback import XBPMFeedback

from hyperion.device_setup_plans import dcm_pitch_roll_mirror_adjuster
from hyperion.device_setup_plans.xbpm_feedback import (
    transmission_and_xbpm_feedback_for_collection_wrapper,
)
from hyperion.parameters.plan_specific.set_energy_internal_params import (
    SetEnergyInternalParameters,
)

UNDULATOR_GROUP = "UNDULATOR_GROUP"


@dataclasses.dataclass
class SetEnergyComposite:
    vfm: FocusingMirror
    vfm_mirror_voltages: VFMMirrorVoltages
    dcm: DCM
    undulator_dcm: UndulatorDCM
    xbpm_feedback: XBPMFeedback
    attenuator: Attenuator


def _set_energy_plan(
    energy_kev,
    composite: SetEnergyComposite,
    internal_params: SetEnergyInternalParameters,
):
    yield from bps.abs_set(composite.undulator_dcm, energy_kev, group=UNDULATOR_GROUP)
    yield from dcm_pitch_roll_mirror_adjuster.adjust_dcm_pitch_roll_vfm_from_lut(
        composite.dcm,
        composite.vfm,
        composite.vfm_mirror_voltages,
        internal_params.beamline_parameters,
        energy_kev,
    )
    yield from bps.wait(group=UNDULATOR_GROUP)
    # XXX Can we move undulator and DCM etc at the same time?


def set_energy_plan(
    energy_kev,
    composite: SetEnergyComposite,
    internal_params: SetEnergyInternalParameters,
):
    yield from transmission_and_xbpm_feedback_for_collection_wrapper(
        _set_energy_plan(energy_kev, composite, internal_params),
        composite.xbpm_feedback,
        composite.attenuator,
        0.1,
    )
