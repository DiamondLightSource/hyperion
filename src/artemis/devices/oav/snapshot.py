import threading
from pathlib import Path

import bluesky.plan_stubs as bps
import requests
from ophyd import Component, Device, DeviceStatus, EpicsSignal, EpicsSignalRO, Signal
from PIL import Image


class Snapshot(Device):
    filename: Signal = Component(Signal)
    directory: Signal = Component(Signal)
    url: EpicsSignal = Component(EpicsSignal, "JPG_URL_RBV", string=True)
    x_size_pv: EpicsSignalRO = Component(EpicsSignalRO, "ArraySize1_RBV")
    y_size_pv: EpicsSignalRO = Component(EpicsSignalRO, "ArraySize2_RBV")
    input_rbpv: EpicsSignalRO = Component(EpicsSignalRO, "NDArrayPort_RBV")
    input_pv: EpicsSignal = Component(EpicsSignal, "NDArrayPort")
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

    def get_sizes_from_pvs(self):
        x_size = yield from bps.rd(self.x_size_pv)
        y_size = yield from bps.rd(self.y_size_pv)
        return x_size, y_size
