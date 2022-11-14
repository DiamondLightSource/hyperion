from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignalRO


class DCM(Device):
    """
    A double crystal monochromator (DCM), used to select the energy of the beam.

    perp describes the gap between the 2 DCM crystals which has to change as you alter
    the angle to select the requested energy.

    offset ensures that the beam exits the DCM at the same point, regardless of energy.
    """

    bragg: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:BRAGG")
    roll: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:ROLL")
    offset: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:OFFSET")
    perp: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:PERP")
    energy: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:ENERGY")
    pitch: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:PITCH")
    wavelength: EpicsMotor = Cpt(EpicsMotor, "-MO-DCM-01:WAVELENGTH")

    # temperatures
    xtal1_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP1")
    xtal2_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP2")
    xtal1_heater_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP3")
    xtal2_heater_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP4")
    backplate_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP5")
    perp_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP6")
    perp_sub_assembly_temp: EpicsSignalRO = Cpt(EpicsSignalRO, "-MO-DCM-01:TEMP7")
