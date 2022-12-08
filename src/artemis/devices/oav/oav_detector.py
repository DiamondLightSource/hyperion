from enum import IntEnum

from ophyd import ADComponent as ADC
from ophyd import (
    AreaDetector,
    CamBase,
    Component,
    Device,
    EpicsSignal,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
)

from artemis.devices.backlight import Backlight
from artemis.devices.motors import I03Smargon
from artemis.devices.oav.grid_overlay import SnapshotWithGrid


class ColorMode(IntEnum):
    """
    Enum to store the various color modes of the camera. We use RGB1.
    """

    MONO = 0
    BAYER = 1
    RGB1 = 2
    RGB2 = 3
    RGB3 = 4
    YUV444 = 5
    YUV422 = 6
    YUV421 = 7


class ZoomController(Device):
    """
    Device to control the zoom level, this is unfortunately on a different prefix
    from CAM.
    """

    percentage: EpicsSignal = Component(EpicsSignal, "ZOOMPOSCMD")

    # Level is the arbitrary level  that corresponds to a zoom percentage.
    # When a zoom is fed in from GDA this is the level it is refering to.
    level: EpicsSignal = Component(EpicsSignal, "MP:SELECT")
    allowed_zooms = ["1.0x", "2.5x", "5.0x", "7.5x", "10.0x"]


class EdgeOutputArrayImageType(IntEnum):
    """
    Enum to store the types of image to tweak the output array. We use Original.
    """

    ORIGINAL = 0
    GREYSCALE = 1
    PREPROCESSED = 2
    CANNY_EDGES = 3
    CLOSED_EDGES = 4


class MXSC(Device):
    """
    Device for edge detection plugin.
    """

    input_plugin_pv: EpicsSignal = Component(EpicsSignal, "NDArrayPort")
    enable_callbacks_pv: EpicsSignal = Component(EpicsSignal, "EnableCallbacks")
    min_callback_time_pv: EpicsSignal = Component(EpicsSignal, "MinCallbackTime")
    blocking_callbacks_pv: EpicsSignal = Component(EpicsSignal, "BlockingCallbacks")
    read_file: EpicsSignal = Component(EpicsSignal, "ReadFile")
    py_filename: EpicsSignal = Component(EpicsSignal, "Filename", string=True)
    preprocess_operation: EpicsSignal = Component(EpicsSignal, "Preprocess")
    preprocess_ksize: EpicsSignal = Component(EpicsSignal, "PpParam1")
    canny_upper_threshold: EpicsSignal = Component(EpicsSignal, "CannyUpper")
    canny_lower_threshold: EpicsSignal = Component(EpicsSignal, "CannyLower")
    close_ksize: EpicsSignal = Component(EpicsSignal, "CloseKsize")
    sample_detection_scan_direction: EpicsSignal = Component(
        EpicsSignal, "ScanDirection"
    )
    sample_detection_min_tip_height: EpicsSignal = Component(
        EpicsSignal, "MinTipHeight"
    )
    tip_x: EpicsSignal = Component(EpicsSignal, "TipX")
    tip_y: EpicsSignal = Component(EpicsSignal, "TipY")
    top: EpicsSignal = Component(EpicsSignal, "Top")
    bottom: EpicsSignal = Component(EpicsSignal, "Bottom")
    output_array: EpicsSignal = Component(EpicsSignal, "OutputArray")
    draw_tip: EpicsSignal = Component(EpicsSignal, "DrawTip")
    draw_edges: EpicsSignal = Component(EpicsSignal, "DrawEdges")


class OAV(AreaDetector):
    cam: CamBase = ADC(CamBase, "-DI-OAV-01:CAM:")
    roi: ADC = ADC(ROIPlugin, "-DI-OAV-01:ROI:")
    proc: ADC = ADC(ProcessPlugin, "-DI-OAV-01:PROC:")
    over: ADC = ADC(OverlayPlugin, "-DI-OAV-01:OVER:")
    tiff: ADC = ADC(OverlayPlugin, "-DI-OAV-01:TIFF:")
    hdf5: ADC = ADC(HDF5Plugin, "-DI-OAV-01:HDF5:")
    snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, "-DI-OAV-01:MJPG:")
    mxsc: MXSC = ADC(MXSC, "-DI-OAV-01:MXSC:")
    zoom_controller: ZoomController = ADC(ZoomController, "-EA-OAV-01:FZOOM:")


if __name__ == "__main__":

    beamline = "BL03I"
    smargon: I03Smargon = I03Smargon(name="smargon", prefix=beamline + "-MO-SGON-01:")
    backlight: Backlight = Component(Backlight, "-EA-BL-01:")
    oav = OAV(name="oav", prefix=beamline)
    oav.wait_for_connection()
