from ophyd import AreaDetector, SingleTrigger, CamBase
from ophyd import ADComponent as ADC
from ophyd import ROIPlugin
#from ophyd import ROIStatNPlugin
from ophyd import ProcessPlugin
from ophyd import OverlayPlugin
from ophyd import TIFFPlugin
from ophyd import HDF5Plugin	#check version
from ophyd import PVAPlugin
from ophyd import ColourConvPlugin

class OAV(AreaDetector):
	cam = ADC(CamBase, "CAM:")
	roi = ADC(ROIPlugin, "ROI:")
	#stat =ADC(ROIStatNPlugin, "STAT:")  # won't import
	proc = ADC(ProcessPlugin, "PROC:") 
	over = ADC(OverlayPlugin, "OVER:") 
	#ffmpeg plugin missing
	tiff = ADC(OverlayPlugin, "TIFF:")
	hdf5 = ADC(HDF5Plugin, "HDF5:")
	#mjpeg plugin missing
	pva = ADC(PVAPlugin, "PVA:")
	#msxc plugin missing
	ccon = ADC(ColourConvPlugin, "CCON:")
	pass

prefix = 'BL03I-DI-OAV-01:'
oav = OAV(prefix, name="oav")


acq=oav.cam.acquire_time.get()

print(oav.over.queue_use.get())
