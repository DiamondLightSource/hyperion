from ophyd import Component as Cpt
from ophyd import Device

from artemis.devices.aperture import Aperture
from artemis.devices.scatterguard import Scatterguard


class ApertureScatterguard(Device):
    aperture: Aperture = Cpt(Aperture, "")
    scatterguard: Scatterguard = Cpt(Scatterguard, "")

    def set_all_positions(
        self,
        aperture_x: float,
        aperture_y: float,
        aperture_z: float,
        scatterguard_x: float,
        scatterguard_y: float,
    ) -> None:
        self.aperture.x.set(aperture_x)
        self.aperture.y.set(aperture_y)
        self.aperture.z.set(aperture_z)
        self.scatterguard.x.set(scatterguard_x)
        self.scatterguard.y.set(scatterguard_y)
