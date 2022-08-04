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


def predict_flux(aperture_size, energy, transmission):
	valid_aperture = {"Large","Medium","Small", "Empty"}
	if aperture_size not in valid_aperture:
		raise ValueError("Aperture size must be one of %r," % valid_aperture)
	if energy <= 5500 or energy >=25000:
		raise ValueError("Energy is required in eV and in range 5500 to 25000eV")
	if transmission < 0 or transmission >1:
		raise ValueError("Transmission should be in fractional notation, between 0 and 1")
	
	class scale(Enum):
		Large = 0.738			
		Medium = 0.336
		Small = 0.084
		Empty = 1

	aperture_scale = float(scale[aperture_size].value)
	energy_eV = float(energy)
	transmission_scale=float(transmission)
		
	print(aperture_scale)
	print(energy)
	print(transmission)
	
	A = -2.104798686e-15
	B = 1.454341082e-10
	C = 3.586744314e-6
	D = 3.599085792e-2
	E = 1.085096504e2
	
	predicted_flux = "{:e}".format(aperture_scale * transmission_scale * (A*energy_eV**4+B*energy_eV**3-C*energy_eV**2+D*energy_eV-E)*1e12)
	print(predicted_flux)





	


