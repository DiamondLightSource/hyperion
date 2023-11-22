import bluesky.plan_stubs as bps
from dodal.devices.DCM import DCM
from dodal.devices.hfm import HFM
from dodal.devices.i0 import I0
from dodal.devices.qbpm1 import QBPM1
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.vfm import VFM
from ophyd import EpicsMotor, EpicsSignalRO

from hyperion.device_setup_plans.peak_finder import (
    PeakFinder,
    SimpleMaximumPeakEstimator,
    SingleScanPassPeakFinder,
)
from hyperion.log import LOGGER
from hyperion.utils.lookup_table import LinearInterpolationLUTConverter

RESET_SLIT_GAP_GROUP = "reset_slit_gap"

PREP_FOR_VFM_GROUP = "prepare_for_vfm_align"
PREP_FOR_HFM_GROUP = "prepare_for_hfm_align"

# Magic values from GDA beamLineSpecificEnergy.py
SLIT_SIZE_WIDE_OPEN_MM = (500, 500)
SLIT_SIZE_LARGE_MM = (500, 60)
SLIT_SIZE_SMALL_MM = (100, 60)

VFM_FINE_PITCH_INITIAL_PRESET_MM = 0.019
VFM_FINE_PITCH_ADJUST_PEAK_WIDTH_MM = 0.012
VFM_FINE_PITCH_ADJUST_STEP_MM = 0.0006

HFM_FINE_PITCH_INITIAL_PRESET_MM = 0.017
HFM_FINE_PITCH_ADJUST_PEAK_WIDTH_MM = 0.016
HFM_FINE_PITCH_ADJUST_STEP_MM = 0.0006

DCM_PITCH_ADJUST_PEAK_WIDTH = 0.075
DCM_PITCH_ADJUST_PEAK_STEP = 0.002


class DCMPitchRollMirrorAdjuster:
    """Auto-adjust the DCM, then re-adjust pitch, roll and vertical + horizontal focusing mirrors."""

    def __init__(
        self,
        dcm: DCM,
        vfm: VFM,
        hfm: HFM,
        qbpm1: QBPM1,
        collimation_slits: S4SlitGaps,
        i0: I0,
        peak_finder: PeakFinder = SingleScanPassPeakFinder(
            SimpleMaximumPeakEstimator()
        ),
    ):
        super().__init__()
        self._i0 = i0
        self._collimation_slits = collimation_slits
        self._peak_finder = peak_finder
        self._dcm = dcm
        self._vfm = vfm
        self._hfm = hfm
        self._qbpm1 = qbpm1

    def auto_adjust_dcm_hfm_vfm_pitch_roll(self):
        """Main entry point
        Args:
        vfm: Vertical Focus Mirror device
        """

        # TODO set transmission 1.0 ???

        # XXX where is this value currently initialised in GDA?
        current_pitch = yield from bps.rd(self._dcm.pitch.user_readback)
        LOGGER.info("DCM Auto Pitch adjustment")
        yield from self._adjust_to_peak(
            self._dcm.pitch,
            self._qbpm1.intensityC,
            current_pitch,
            DCM_PITCH_ADJUST_PEAK_WIDTH,
            DCM_PITCH_ADJUST_PEAK_STEP,
        )

        # XXX GDA waits here for 2 seconds, not sure what we are waiting for here?
        yield from bps.sleep(2)

        yield from self._adjust_dcm_roll(PREP_FOR_VFM_GROUP)

        LOGGER.info(
            f"Applying fine pitch initial HFM preset = {HFM_FINE_PITCH_INITIAL_PRESET_MM}, VFM preset = {VFM_FINE_PITCH_INITIAL_PRESET_MM}"
        )
        # adjust HFM fine pitch
        yield from bps.abs_set(
            self._hfm.fine_pitch_mm,
            HFM_FINE_PITCH_INITIAL_PRESET_MM,
            group=PREP_FOR_VFM_GROUP,
        )
        # adjust VFM fine pitch
        yield from bps.abs_set(
            self._vfm.fine_pitch_mm,
            VFM_FINE_PITCH_INITIAL_PRESET_MM,
            group=PREP_FOR_VFM_GROUP,
        )

        # set slit size big
        yield from self._adjust_slit_size(*SLIT_SIZE_LARGE_MM, PREP_FOR_VFM_GROUP)

        yield from bps.wait(PREP_FOR_VFM_GROUP)

        LOGGER.info("VFM Auto Pitch adjustment")
        yield from self._adjust_to_peak(
            self._vfm.fine_pitch_mm,
            self._i0.intensity,
            VFM_FINE_PITCH_INITIAL_PRESET_MM,
            VFM_FINE_PITCH_ADJUST_PEAK_WIDTH_MM,
            VFM_FINE_PITCH_ADJUST_STEP_MM,
        )
        # set slit size small
        yield from self._adjust_slit_size(*SLIT_SIZE_SMALL_MM, PREP_FOR_HFM_GROUP)
        yield from bps.wait(PREP_FOR_HFM_GROUP)

        LOGGER.info("HFM Auto Pitch adjustment")
        yield from self._adjust_to_peak(
            self._hfm.fine_pitch_mm,
            self._i0.intensity,
            HFM_FINE_PITCH_INITIAL_PRESET_MM,  # XXX in GDA this is 0.0174 instead of 0.017, is this deliberate?
            HFM_FINE_PITCH_ADJUST_PEAK_WIDTH_MM,
            HFM_FINE_PITCH_ADJUST_STEP_MM,
        )

        yield from self._adjust_slit_size(*SLIT_SIZE_WIDE_OPEN_MM, RESET_SLIT_GAP_GROUP)
        yield from bps.wait(RESET_SLIT_GAP_GROUP)
        # TODO reset attenuation?

    def _adjust_dcm_roll(self, group=None):
        bragg_deg = yield from bps.rd(self._dcm.bragg_in_degrees.user_readback)
        # convert to target roll value
        bragg_angle_deg_to_roll_mrad_converter = LinearInterpolationLUTConverter(
            self._dcm.dcm_roll_converter_lookup_table_path
        )
        target_roll_mrad = bragg_angle_deg_to_roll_mrad_converter.s_to_t(bragg_deg)
        LOGGER.info(f"Adjusting DCM roll to {target_roll_mrad}")
        # XXX bps.mv fails due to hasattr(o, 'RealPosition') raising AttributeError
        yield from bps.abs_set(self._dcm.roll_in_mrad, target_roll_mrad, group=group)

    # goToPeak.goToPeakGaussian2(self.scriptcontroller,
    # self.pitchScannable,  <-- x
    # self.jythonNameMap.qbpm1c, <-- y
    # self.pitchScannable(), <-- centre
    # 0.075, <-- width
    # 0.002) <-- step
    def _adjust_to_peak(self, x: EpicsMotor, y: EpicsSignalRO, centre, width, step):
        """Adjust the vertical focus mirror to find the optimal peak.
        Args:
        x: independent variable e.g. motor to adjust
        y: dependent variable e.g. intensity monitor
        centre: estimated centre of peak to find
        width: estimated width of peak to find
        step: scan step"""
        LOGGER.info(
            f"Searching for peak in centre={centre}, width={width}, step={step}"
        )
        yield from self._peak_finder.find_peak_plan(x, y, centre, width, step)

    def _adjust_slit_size(self, xgap_mm, ygap_mm, group):
        LOGGER.info(f"Adjusting slits to ({xgap_mm, ygap_mm})")
        yield from bps.abs_set(self._collimation_slits.xgap, xgap_mm, group=group)
        yield from bps.abs_set(self._collimation_slits.ygap, ygap_mm, group=group)
