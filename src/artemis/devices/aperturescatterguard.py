from ophyd import Component as Cpt
from ophyd import Device
from ophyd.status import AndStatus

from artemis.devices.aperture import Aperture
from artemis.devices.scatterguard import Scatterguard
from artemis.parameters import AperturePositions


class ApertureScatterguard(Device):
    aperture: Aperture = Cpt(Aperture, "")
    scatterguard: Scatterguard = Cpt(Scatterguard, "")
    aperture_positions = AperturePositions

    def __init__(self, positions: AperturePositions, *args, **kwargs):
        self.aperture_positions = positions
        super.__init__(*args, **kwargs)

    def safe_move_within_datacollection_range(
        self,
        aperture_x: float,
        aperture_y: float,
        aperture_z: float,
        scatterguard_x: float,
        scatterguard_y: float,
    ) -> None:
        """
        Move the aperture and scatterguard combo safely to a new position -
        """
        current_ap_z = self.aperture.x.user_readback.get()
        if aperture_z != current_ap_z != self.aperture_positions.SMALL[2]:
            raise Exception(
                "ApertureScatterguard safe move is not yet defined for positions "
                "outside of LARGE, MEDIUM, SMALL, ROBOT_LOAD."
            )

        current_ap_y = self.aperture.x.user_readback.get()
        if aperture_y > current_ap_y:
            sg_status: AndStatus = self.scatterguard.x.set(
                scatterguard_x
            ) & self.scatterguard.y.set(scatterguard_y)
            sg_status.wait()
            self.aperture.x.set(aperture_x)
            self.aperture.y.set(aperture_y)
            self.aperture.z.set(aperture_z)

        else:
            ap_status: AndStatus = (
                self.aperture.x.set(aperture_x)
                & self.aperture.y.set(aperture_y)
                & self.aperture.z.set(aperture_z)
            )
            ap_status.wait()
            self.scatterguard.x.set(scatterguard_x)
            self.scatterguard.y.set(scatterguard_y)
