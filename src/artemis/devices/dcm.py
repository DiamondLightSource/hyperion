from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignalRO


class DCM(Device):

    # upstream_x: EpicsMotor = Cpt(EpicsMotor, '-MO-DET-01:UPSTREAMX')

    bragg: EpicsMotor = Cpt(EpicsMotor, ":BRAGG")
    roll: EpicsMotor = Cpt(EpicsMotor, ":ROLL")
    offset: EpicsMotor = Cpt(EpicsMotor, ":OFFSET")
    perp: EpicsMotor = Cpt(EpicsMotor, ":PERP")
    energy: EpicsMotor = Cpt(EpicsMotor, ":ENERGY")
    energy_rbv: EpicsSignalRO = Cpt(EpicsSignalRO, ":ENERGY.RBV")
    pitch: EpicsMotor = Cpt(EpicsMotor, ":PITCH")
    wavelength: EpicsMotor = Cpt(EpicsMotor, ":WAVELENGTH")

    # temperatures
    xtal1_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP1")
    xtal2_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP2")
    xtal1_heater_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP3")
    xtal2_heater_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP4")
    backplate_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP5")
    perp_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP6")
    perp_sub_assembly_temp: EpicsSignalRO = Cpt(EpicsSignalRO, ":TEMP7")
