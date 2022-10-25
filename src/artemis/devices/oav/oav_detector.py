from ophyd import ADComponent as ADC
from ophyd import (  # EpicsSignal, EpicsSignalWithRBV
    AreaDetector,
    CamBase,
    Component,
    EpicsSignalRO,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
)

from artemis.devices.oav.grid_overlay import SnapshotWithGrid


class OAV(AreaDetector):
    # signal that was here before
    on: EpicsSignalRO = Component(EpicsSignalRO, "ProcessConnected_RBV")

    # snapshot PVs
    snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, ":MJPG")
    cam = ADC(CamBase, "CAM:")
    roi = ADC(ROIPlugin, "ROI:")
    proc = ADC(ProcessPlugin, "PROC:")
    over = ADC(OverlayPlugin, "OVER:")
    tiff = ADC(OverlayPlugin, "TIFF:")
    hdf5 = ADC(HDF5Plugin, "HDF5:")
    # snapshot: SnapshotWithGrid = Component(SnapshotWithGrid, ":MJPG")

    # Edge detection PVs
    oavColourMode: EpicsSignalRO = Component(EpicsSignalRO, "CAM:ColorMode")
    xSizePV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize1_RBV")
    ySizePV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:ArraySize2_RBV")
    inputRBPV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:NDArrayPort_RBV")
    exposureRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquireTime_RBV")
    acqPeriodRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquirePeriod_RBV")
    gainRBPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:Gain_RBV")
    inputPV: EpicsSignalRO = Component(EpicsSignalRO, "MJPG:NDArrayPort")
    exposurePV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquireTime")
    acqPeriodPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:AcquirePeriod")
    gainPV: EpicsSignalRO = Component(EpicsSignalRO, "CAM:Gain")
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

    edgeTop: EpicsSignalRO = Component(EpicsSignalRO, "MXSC:Top")
    edgeBottom: EpicsSignalRO = Component(EpicsSignalRO, "MXSC:Bottom")


if __name__ == "__main__":

    from matplotlib import pyplot as plt

    beamline = "BL04I"
    oav = OAV(name="oav", prefix=f"{beamline}-DI-OAV-01:")
    oav.wait_for_connection()
    bottom = oav.edgeBottom.read()
    bottom = bottom["oav_edgeBottom"]["value"]
    top = oav.edgeTop.read()
    top = top["oav_edgeTop"]["value"]
    print(len(top))
    print(len(bottom))
    plt.plot(range(len(bottom)), bottom, range(len(top)), top)
    plt.show()
