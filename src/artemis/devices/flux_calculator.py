import time

from ophyd import Component, Device, EpicsSignalRO, Signal


class FluxCalculator(Device):
    aperture_size_signal: Signal = Component(Signal)
    energy_signal = Component(EpicsSignalRO, "-MO-DCM-01:ENERGY.RBV")
    intensity_signal = Component(EpicsSignalRO, "-EA-XBPM-02:SumAll:MeanValue_RBV")

    flux: Signal = Component(Signal, name="flux", kind="normal", attr_name="flux_value")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def update_flux(*_, **__):
            new_value = self.calculate_flux()
            self.flux.put(new_value)

        self.energy_signal.subscribe(update_flux)
        self.intensity_signal.subscribe(update_flux)

    def get_flux(self):
        time.sleep(0.5)
        return self.flux.get()

    def calculate_flux(self):
        # polynomial fit coefficients for XBPM2 response to energy
        A = 5.393959225e-13
        B = 1.321301118e-8
        C = 4.768760712e-4
        D = 2.118311635
        E = self.energy_signal.get() * 1000

        gradient = A * E**3 - B * E**2 + C * E - D

        signal = self.intensity_signal.get() / 1e-6

        flux = 1e12 * signal * gradient

        flux_at_sample = flux * self.aperture_size_signal.get()

        return flux_at_sample
