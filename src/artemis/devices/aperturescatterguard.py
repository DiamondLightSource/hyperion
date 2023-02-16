from dataclasses import dataclass
from typing import Optional

from ophyd import Component as Cpt
from ophyd.status import AndStatus

from artemis.devices.aperture import Aperture
from artemis.devices.logging_ophyd_device import InfoLoggingDevice
from artemis.devices.scatterguard import Scatterguard


@dataclass
class AperturePositions:
    """Holds tuples (miniap_x, miniap_y, miniap_z, scatterguard_x, scatterguard_y)
    representing the motor positions needed to select a particular aperture size.
    """

    LARGE: tuple[float, float, float, float, float]
    MEDIUM: tuple[float, float, float, float, float]
    SMALL: tuple[float, float, float, float, float]
    ROBOT_LOAD: tuple[float, float, float, float, float]

    @classmethod
    def from_gda_beamline_params(cls, params):
        return cls(
            LARGE=(
                params["miniap_x_LARGE_APERTURE"],
                params["miniap_y_LARGE_APERTURE"],
                params["miniap_z_LARGE_APERTURE"],
                params["sg_x_LARGE_APERTURE"],
                params["sg_y_LARGE_APERTURE"],
            ),
            MEDIUM=(
                params["miniap_x_MEDIUM_APERTURE"],
                params["miniap_y_MEDIUM_APERTURE"],
                params["miniap_z_MEDIUM_APERTURE"],
                params["sg_x_MEDIUM_APERTURE"],
                params["sg_y_MEDIUM_APERTURE"],
            ),
            SMALL=(
                params["miniap_x_SMALL_APERTURE"],
                params["miniap_y_SMALL_APERTURE"],
                params["miniap_z_SMALL_APERTURE"],
                params["sg_x_SMALL_APERTURE"],
                params["sg_y_SMALL_APERTURE"],
            ),
            ROBOT_LOAD=(
                params["miniap_x_ROBOT_LOAD"],
                params["miniap_y_ROBOT_LOAD"],
                params["miniap_z_ROBOT_LOAD"],
                params["sg_x_ROBOT_LOAD"],
                params["sg_y_ROBOT_LOAD"],
            ),
        )

    def position_valid(self, pos: tuple[float, float, float, float, float]):
        """
        Check if argument 'pos' is a valid position in this AperturePositions object.
        """
        if pos not in [self.LARGE, self.MEDIUM, self.SMALL, self.ROBOT_LOAD]:
            return False
        return True


class ApertureScatterguard(InfoLoggingDevice):
    aperture: Aperture = Cpt(Aperture, "-MO-MAPT-01:")
    scatterguard: Scatterguard = Cpt(Scatterguard, "-MO-SCAT-01:")
    aperture_positions: Optional[AperturePositions] = None

    def load_aperture_positions(self, positions: AperturePositions):
        self.aperture_positions = positions

    def set(self, pos: tuple[float, float, float, float, float]):
        assert isinstance(self.aperture_positions, AperturePositions)
        assert self.aperture_positions.position_valid(pos)
        self._safe_move_within_datacollection_range(*pos)

    def _safe_move_within_datacollection_range(
        self,
        aperture_x: float,
        aperture_y: float,
        aperture_z: float,
        scatterguard_x: float,
        scatterguard_y: float,
    ) -> None:
        """
        Move the aperture and scatterguard combo safely to a new position
        """
        # EpicsMotor does not have deadband/MRES field, so the way to check if we are
        # in a datacollection position is to see if we are "ready" (DMOV) and the target
        # position is correct
        ap_z_in_position = self.aperture.z.motor_done_move.get()
        if not ap_z_in_position:
            return
        current_ap_z = self.aperture.z.user_setpoint.get()
        if current_ap_z != aperture_z:
            raise Exception(
                "ApertureScatterguard safe move is not yet defined for positions "
                "outside of LARGE, MEDIUM, SMALL, ROBOT_LOAD."
            )

        current_ap_y = self.aperture.y.user_readback.get()
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
