from ophyd import Component, Device, Signal

from artemis.devices.dcm import DCM
from artemis.devices.xbpm2 import XBPM2


class FluxCalculator(Device):
    aperture_size_signal: Signal = Component(Signal)
    dcm: DCM = DCM(name="DCM", prefix="BL03I-MO-DCM-01")
    xbpm2: XBPM2 = XBPM2(name="XBPM2", prefix="BL03I-EA-XBPM-02")

    def get_flux(self):
        # polynomial fit coefficients for XBPM2 response to energy
        A = 5.393959225e-13
        B = 1.321301118e-8
        C = 4.768760712e-4
        D = 2.118311635
        energy = self.dcm.energy_rbv.get()
        E = energy * 1000

        gradient = A * E**3 - B * E**2 + C * E - D

        signal = self.xbpm2.intensity.get() / 1e-6

        flux = float(1e12 * signal * gradient)

        flux_at_sample = flux * self.aperture_size_signal.get()

        print(f"{flux_at_sample=}")
        return flux_at_sample
