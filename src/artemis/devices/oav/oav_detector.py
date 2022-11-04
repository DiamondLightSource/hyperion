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


class Camera(CamBase):
    zoom: EpicsSignal = Component(EpicsSignal, "FZOOM:ZOOMPOSCMD")


class Backlight(Device):
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


if __name__ == "__main__":

    beamline = "BL04I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01:")
    oav.wait_for_connection()
