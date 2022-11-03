from ophyd import ADComponent as ADC
from ophyd import (
    AreaDetector,
    CamBase,
    Component,
    Device,
    EpicsMotor,
    EpicsSignal,
    EpicsSignalRO,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
)

from artemis.devices.oav.grid_overlay import SnapshotWithGrid


class Goniometer(Device):
    omega: EpicsMotor = Component(EpicsMotor, "OMEGA")
    x: EpicsMotor = Component(EpicsMotor, "X")
    y: EpicsMotor = Component(EpicsMotor, "Y")
    z: EpicsMotor = Component(EpicsMotor, "Z")


class Camera(AreaDetector):
    zoom: EpicsSignal = Component(EpicsSignal, "FZOOM:ZOOMPOSCMD")


class Backlight(AreaDetector):
    control: EpicsSignal = Component(EpicsSignal, "CTRL")


class OAV(AreaDetector):
    # signal that was here before
    # on: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")

    # snapshot PVs
    cam = ADC(CamBase, "CAM:")
    roi = ADC(ROIPlugin, "ROI:")
    proc = ADC(ProcessPlugin, "PROC:")
    over = ADC(OverlayPlugin, "OVER:")
    tiff = ADC(OverlayPlugin, "TIFF:")
    hdf5 = ADC(HDF5Plugin, "HDF5:")
    snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, "MJPG")

    # Edge detection PVs
    oavColourMode: EpicsSignal = Component(EpicsSignal, "CAM:ColorMode")
    xSizePV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize1_RBV")
    ySizePV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize2_RBV")
    inputRBPV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:NDArrayPort_RBV")
    exposureRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquireTime_RBV")
    acqPeriodRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquirePeriod_RBV")
    gainRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:Gain_RBV")
    inputPV: EpicsSignal = Component(EpicsSignal, "MJPG:NDArrayPort")
    exposurePV: EpicsSignal = Component(EpicsSignal, "CAM:AcquireTime")
    acqPeriodPV: EpicsSignal = Component(EpicsSignal, "CAM:AcquirePeriod")
    gainPV: EpicsSignal = Component(EpicsSignal, "CAM:Gain")
    enableOverlayPV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:EnableCallbacks")
    overlayPortPV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:NDArrayPort")
    useOverlay1PV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:1:Use")
    useOverlay2PV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Use")
    overlay2ShapePV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Shape")
    overlay2RedPV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Red")
    overlay2GreenPV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Green")
    overlay2BluePV: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:Blue")
    overlay2XPosition: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:PositionX")
    overlay2YPosition: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:PositionY")
    overlay2XSize: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:SizeX")
    overlay2YSize: EpicsSignalRO = Component(EpicsSignalRO, "OVER:2:SizeY")

    # MXSC signals
    input_plugin_pv: EpicsSignal = Component(EpicsSignal, "MXSC:NDArrayPort")
    enable_callbacks_pv: EpicsSignal = Component(EpicsSignal, "MXSC:EnableCallbacks")
    min_callback_time_pv: EpicsSignal = Component(EpicsSignal, "MXSC:MinCallbackTime")
    blocking_callbacks_pv: EpicsSignal = Component(
        EpicsSignal, "MXSC:BlockingCallbacks"
    )
    read_file_pv: EpicsSignal = Component(EpicsSignal, "MXSC:ReadFile")
    py_filename_pv: EpicsSignal = Component(EpicsSignal, "MXSC:Filename")
    py_filename_rbpv: EpicsSignal = Component(EpicsSignal, "MXSC:Filename_RBV")
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

    def start_mxsc(self, input_plugin, min_callback_time, filename=None):
        self.input_plugin_pv.put(input_plugin)
        self.enable_callbacks_pv.put(1)
        self.min_callback_time_pv.put(min_callback_time)
        self.blocking_callbacks_pv.put(0)

        # I03-323
        if filename is not None:  # and filename != self.py_filename_rbpv.get():
            self.py_filename_pv.put(filename)
            self.read_file_pv.put(1)

        # Image annotations
        self.draw_tip_pv.put(True)
        self.draw_edges_pv.put(True)

        # Image to send downstream
        OUTPUT_ORIGINAL = 0
        self.output_array_pv.put(OUTPUT_ORIGINAL)


if __name__ == "__main__":

    beamline = "BL04I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01:")
    oav.wait_for_connection()
    print(oav.acqPeriodPV.get())
