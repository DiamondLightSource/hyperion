from ophyd import Component as Cpt
from ophyd import EpicsMotor
from ophyd.epics_motor import MotorBundle

from artemis.devices.motors import MotorLimitHelper, XYZLimitBundle


class I03Smargon(MotorBundle):
    """
    Real motors removed for testing with S03 until they are added
    """

    x: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:X")
    y: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:Y")
    z: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:Z")
    chi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:CHI")
    phi: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:PHI")
    omega: EpicsMotor = Cpt(EpicsMotor, "-MO-SGON-01:OMEGA")

    def get_xyz_limits(self) -> XYZLimitBundle:
        """Get the limits for the x, y and z axes.

        Note that these limits may not yet be valid until wait_for_connection is called
        on this MotorBundle.

        Returns:
            XYZLimitBundle: The limits for the underlying motors.
        """
        return XYZLimitBundle(
            MotorLimitHelper(self.x),
            MotorLimitHelper(self.y),
            MotorLimitHelper(self.z),
        )
