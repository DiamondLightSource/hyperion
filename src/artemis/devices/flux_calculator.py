from bluesky import RunEngine
from ophyd import Component, Device, Signal

from artemis.devices.dcm import DCM
from artemis.devices.xbpm2 import XBPM2


class FluxCalculator(Device):
    aperture_size_signal: Signal = Component(Signal)
    dcm: DCM = DCM(name="DCM", prefix="BL03I-MO-DCM-01")
    xbpm2: XBPM2 = XBPM2(name="XBPM2", prefix="BL03I-EA-XBPM-02")

    flux: Signal = Component(Signal, name="flux", kind="normal", attr_name="flux_value")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flux.subscribe(self.get_flux2)

    @property
    def flux_value(self):
        print("Has been called")
        return self.get_flux()

    def get_flux2(self, *_, **__):
        return self.get_flux()

    def get_flux(self):
        print("Called")
        # polynomial fit coefficients for XBPM2 response to energy
        A = 5.393959225e-13
        B = 1.321301118e-8
        C = 4.768760712e-4
        D = 2.118311635
        E = self.dcm.energy_rbv.get() * 1000

        gradient = A * E**3 - B * E**2 + C * E - D

        signal = self.xbpm2.intensity.get() / 1e-6

        flux = 1e12 * signal * gradient

        flux_at_sample = flux * self.aperture_size_signal.get()

        return flux_at_sample

    def read(self, *args, **kwargs):
        self.flux.put(self.get_flux())
        return super().read(*args, **kwargs)


if __name__ == "__main__":
    RE = RunEngine()
    calc = FluxCalculator(name="calc", read_attrs=["flux"])
    calc.wait_for_connection()
    calc.trigger()
    calc.flux.put(1)
    print(f"{calc.read()=}")
    # RE(rd(calc))
