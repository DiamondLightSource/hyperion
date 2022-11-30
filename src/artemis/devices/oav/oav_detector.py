from enum import IntEnum

import bluesky.plan_stubs as bps
import numpy as np
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

    zoom: EpicsSignal = Component(EpicsSignal, "ZOOMPOSCMD")


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

    def get_edge_waveforms(self):
        """
        Get the waveforms from the PVs as numpy arrays.
        """
        yield from bps.rd(self.top)
        yield from bps.rd(self.bottom)

    def get_edge_waveforms_as_numpy_arrays(self):
        return (np.array(pv) for pv in tuple(self.get_edge_waveforms()))

    def start_mxsc(self, input_plugin, min_callback_time, filename):
        """
        Sets PVs relevant to edge detection plugin.

        Args:
            input_plugin: link to the camera stream
            min_callback_time: the value to set the minimum callback time to
            filename: filename of the python script to detect edge waveforms from camera stream.
        Returns: None
        """
        yield from bps.abs_set(self.input_plugin_pv, input_plugin)

        # Turns the area detector plugin on
        yield from bps.abs_set(self.enable_callbacks_pv, 1)

        # Set the minimum time between updates of the plugin
        yield from bps.abs_set(self.min_callback_time_pv, min_callback_time)

        # Stop the plugin from blocking the IOC and hogging all the CPU
        yield from bps.abs_set(self.blocking_callbacks_pv, 0)

        # Set the python file to use for calculating the edge waveforms
        yield from bps.abs_set(self.py_filename, filename, wait=True)
        yield from bps.abs_set(self.read_file, 1)

        # Image annotations
        yield from bps.abs_set(self.draw_tip, True)
        yield from bps.abs_set(self.draw_edges, True)

        # Use the original image type for the edge output array
        yield from bps.abs_set(self.output_array, EdgeOutputArrayImageType.ORIGINAL)


class OAV(AreaDetector):
    cam: CamBase = ADC(CamBase, "-EA-OAV-01:CAM:")
    roi: ADC = ADC(ROIPlugin, "-DI-OAV-01:ROI:")
    proc: ADC = ADC(ProcessPlugin, "-DI-OAV-01:PROC:")
    over: ADC = ADC(OverlayPlugin, "-DI-OAV-01:OVER:")
    tiff: ADC = ADC(OverlayPlugin, "-DI-OAV-01:TIFF:")
    hdf5: ADC = ADC(HDF5Plugin, "-DI-OAV-01:HDF5:")
    snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, "-DI-OAV-01:MJPG:")
    mxsc: MXSC = ADC(MXSC, "-DI-OAV-01:MXSC:")
    zoom_controller: ZoomController = ADC(ZoomController, "-EA-OAV-01-FZOOM:")


if __name__ == "__main__":

    beamline = "S03SIM"
    smargon: I03Smargon = Component(I03Smargon, "-MO-SGON-01:")
    backlight: Backlight = Component(Backlight, "-EA-BL-01:")
    oav = OAV(name="oav", prefix=beamline)
    oav.wait_for_connection()
