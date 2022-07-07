from ophyd import ADComponent as ADC
from ophyd import (
    AreaDetector,
    CamBase,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
)


class OAV(AreaDetector):
    cam = ADC(CamBase, "CAM:")
    roi = ADC(ROIPlugin, "ROI:")
    proc = ADC(ProcessPlugin, "PROC:")
    over = ADC(OverlayPlugin, "OVER:")
    tiff = ADC(OverlayPlugin, "TIFF:")
    hdf5 = ADC(HDF5Plugin, "HDF5:")
