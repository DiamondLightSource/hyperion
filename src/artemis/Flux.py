from bluesky import RunEngine
from devices.XBPM2 import XBPM2
from devices.DCM import DCM
from enum import Enum
import bluesky.plans as bp
import bluesky.plan_stubs as bps

RE = RunEngine({})


xbpm2 = XBPM2(name="XBPM2", prefix="BL03I")
dcm = DCM(name="DCM", prefix="BL03I")

xbpm2.wait_for_connection()
dcm.wait_for_connection()




def get_flux(aperture_size):

	valid = {"Large","Medium","Small", "Empty"}
	if aperture_size not in valid:
		raise ValueError("Aperture size must be one of %r," % valid)
	
	class scale(Enum):
		Large = 0.738			#aperture scales to be applied to XBPM2 reading to give flux at sample
		Medium = 0.336
		Small = 0.084
		Empty = 1

	aperture_scale = float(scale[aperture_size].value)


	A = 5.393959225e-13			# polynomial fit coefficients for XBPM2 response to energy
	B = 1.321301118e-8			#
	C = 4.768760712e-4			#
	D = 2.118311635				#
	E = (yield from bps.rd(dcm.energy))*1000
	
	gradient = (A*E**3-B*E**2+C*E-D)
	
	signal = (yield from bps.rd(xbpm2.intensity))/1e-6
	
	flux = float(1e12 * signal * gradient)

	flux_at_sample = "{:e}".format(flux * aperture_scale)
	
	print(flux_at_sample)


RE(get_flux("Large"))
RE(get_flux("Medium"))
RE(get_flux("Small"))	
RE(get_flux("Empty"))

	


