from enum import IntEnum

import bluesky.plan_stubs as bps
import numpy as np
from ophyd import ADComponent as ADC
from ophyd import (
    AreaDetector,
    CamBase,
    Component,
    EpicsSignal,
    EpicsSignalRO,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
)

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


class Camera(CamBase):
    zoom: EpicsSignal = Component(EpicsSignal, "FZOOM:ZOOMPOSCMD")


class EdgeOutputArrayImageType(IntEnum):
    """
    Enum to store the types of image to tweak the output array. We use Original.
    """

    ORIGINAL = 0
    GREYSCALE = 1
    PREPROCESSED = 2
    CANNY_EDGES = 3
    CLOSED_EDGES = 4


class OAV(AreaDetector):
    # signal that was here before
    # on: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")

    # snapshot PVs
    cam: ADC = ADC(CamBase, "CAM:")
    roi: ADC = ADC(ROIPlugin, "ROI:")
    proc: ADC = ADC(ProcessPlugin, "PROC:")
    over: ADC = ADC(OverlayPlugin, "OVER:")
    tiff: ADC = ADC(OverlayPlugin, "TIFF:")
    hdf5: ADC = ADC(HDF5Plugin, "HDF5:")
    snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, "MJPG")

    # Edge detection PVs
    colour_mode_pv: EpicsSignal = Component(EpicsSignal, "CAM:ColorMode")
    x_size_pv: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize1_RBV")
    y_size_pv: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize2_RBV")
    input_rbpv: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:NDArrayPort_RBV")
    exposure_rbpv: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquireTime_RBV")
    acquire_period_rbpv: EpicsSignalRO = Component(
        EpicsSignalRO, "CAM:AcquirePeriod_RBV"
    )
    gain_rbpv: EpicsSignalRO = Component(EpicsSignalRO, "CAM:Gain_RBV")
    input_pv: EpicsSignal = Component(EpicsSignal, "MJPG:NDArrayPort")
    exposure_pv: EpicsSignal = Component(EpicsSignal, "CAM:AcquireTime")
    acquire_period_pv: EpicsSignal = Component(EpicsSignal, "CAM:AcquirePeriod")
    gain_pv: EpicsSignal = Component(EpicsSignal, "CAM:Gain")
    enable_overlay_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:EnableCallbacks")
    overlay_port_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:NDArrayPort")
    use_overlay1_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:1:Use")
    use_overlay2_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Use")
    overlay2_shape_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Shape")
    overlay2_red_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Red")
    overlay2_green_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Green")
    overlay2_blue_pv: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Blue")
    overlay2_x_position: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:PositionX")
    overlay2_y_position: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:PositionY")
    overlay2_x_size: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:SizeX")
    overlay2_y_size: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:SizeY")

    # MXSC signals
    input_plugin_pv: EpicsSignal = Component(EpicsSignal, "MXSC:NDArrayPort")
    enable_callbacks_pv: EpicsSignal = Component(EpicsSignal, "MXSC:EnableCallbacks")
    min_callback_time_pv: EpicsSignal = Component(EpicsSignal, "MXSC:MinCallbackTime")
    blocking_callbacks_pv: EpicsSignal = Component(
        EpicsSignal, "MXSC:BlockingCallbacks"
    )
    read_file_pv: EpicsSignal = Component(EpicsSignal, "MXSC:ReadFile")
    py_filename_pv: EpicsSignal = Component(EpicsSignal, "MXSC:Filename", string=True)
    py_filename_rbpv: EpicsSignal = Component(
        EpicsSignal, "MXSC:Filename_RBV", string=True
    )
    preprocess_operation_pv: EpicsSignal = Component(EpicsSignal, "MXSC:Preprocess")
    preprocess_ksize_pv: EpicsSignal = Component(EpicsSignal, "MXSC:PpParam1")
    canny_upper_threshold_pv: EpicsSignal = Component(EpicsSignal, "MXSC:CannyUpper")
    canny_lower_threshold_pv: EpicsSignal = Component(EpicsSignal, "MXSC:CannyLower")
    close_ksize_pv: EpicsSignal = Component(EpicsSignal, "MXSC:CloseKsize")
    sample_detection_scan_direction_pv: EpicsSignal = Component(
        EpicsSignal, "MXSC:ScanDirection"
    )
    sample_detection_min_tip_height_pv: EpicsSignal = Component(
        EpicsSignal, "MXSC:MinTipHeight"
    )
    tip_x_pv: EpicsSignal = Component(EpicsSignal, "MXSC:TipX")
    tip_y_pv: EpicsSignal = Component(EpicsSignal, "MXSC:TipY")
    top_pv: EpicsSignal = Component(EpicsSignal, "MXSC:Top")
    bottom_pv: EpicsSignal = Component(EpicsSignal, "MXSC:Bottom")
    output_array_pv: EpicsSignal = Component(EpicsSignal, "MXSC:OutputArray")
    draw_tip_pv: EpicsSignal = Component(EpicsSignal, "MXSC:DrawTip")
    draw_edges_pv: EpicsSignal = Component(EpicsSignal, "MXSC:DrawEdges")

    def get_edge_waveforms(self):
        """
        Get the waveforms from the PVs as numpy arrays.
        """
        yield from bps.rd(self.top_pv)
        yield from bps.rd(self.bottom_pv)

    def get_edge_waveforms_as_numpy_arrays(self):
        return (np.array(pv) for pv in tuple(self.get_edge_waveforms()))
