from ophyd import Device, EpicsSignal,EpicsSignalRO, EpicsSignalWithRBV, EpicsMotor
from ophyd import Component as Cpt

class FluorescenceDetector(Device):
	IN=1
	OUT=0
	pos: EpicsSignal = Cpt(EpicsSignal,'-EA-FLU-01:CTRL')
	
class Xspress3Mini(Device):
	acquire: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:Acquire')	
	acquire_time: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:AcquireTime')
	num_images: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:NumImages')
	DTC_energy: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:DTC_ENERGY')
	filepath: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV, '-EA-XSP3-01:HDF5:FilePath', string=True, kind='config')
	filepath_exists: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:HDF5:FilePathExists_RBV')
	filename: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV, '-EA-XSP3-01:HDF5:FileName', string=True, kind='config')
	filenumber: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV, '-EA-XSP3-01:HDF5:FileNumber', string=True, kind='config')
	capture: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:HDF5:Capture')

	sca5_low_limit: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:C1_SCA5_LLM')
	sca5_high_limit: EpicsSignalWithRBV = Cpt(EpicsSignalWithRBV,'-EA-XSP3-01:C1_SCA5_HLM')

	sca0_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA0:Value_RBV')
	sca1_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA1:Value_RBV')
	sca2_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA2:Value_RBV')
	sca3_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA3:Value_RBV')
	sca4_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA4:Value_RBV')
	sca5_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA5:Value_RBV')	
	sca6_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA6:Value_RBV')	
	sca7_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA7:Value_RBV')
	sca8_value: EpicsSignalRO = Cpt(EpicsSignalRO, '-EA-XSP3-01:C1_SCA8:Value_RBV')


