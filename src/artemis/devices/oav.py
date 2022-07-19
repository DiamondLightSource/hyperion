import threading
from pathlib import Path

import requests
from ophyd import ADComponent as ADC
from ophyd import (
    AreaDetector,
    CamBase,
    Component,
    Device,
    DeviceStatus,
    EpicsSignal,
    HDF5Plugin,
    OverlayPlugin,
    ProcessPlugin,
    ROIPlugin,
    Signal,
)
from PIL import Image


class Snapshot(Device):
    filename: Signal = Component(Signal)
    directory: Signal = Component(Signal)
    url: EpicsSignal = Component(EpicsSignal, ":JPG_URL_RBV", string=True)
    KICKOFF_TIMEOUT: float = 10.0

    def trigger(self):
        st = DeviceStatus(device=self, timeout=self.KICKOFF_TIMEOUT)
        url_str = self.url.get()
        filename_str = self.filename.get()
        directory_str = self.directory.get()

        def get_snapshot():
            try:
                response = requests.get(url_str, stream=True)
                response.raise_for_status()
                image = Image.open(response.raw)
                image_path = Path(f"{directory_str}/{filename_str}.png")
                image.save(image_path)
                self.post_processing(image)
                st.set_finished()
            except requests.HTTPError as e:
                st.set_exception(e)

        threading.Thread(target=get_snapshot, daemon=True).start()

        return st

    def post_processing(self, image: Image.Image):
        pass


class OAV(AreaDetector):
    cam = ADC(CamBase, "CAM:")
    roi = ADC(ROIPlugin, "ROI:")
    proc = ADC(ProcessPlugin, "PROC:")
    over = ADC(OverlayPlugin, "OVER:")
    tiff = ADC(OverlayPlugin, "TIFF:")
    hdf5 = ADC(HDF5Plugin, "HDF5:")
    snapshot: Snapshot = Component(Snapshot, ":MJPG")
