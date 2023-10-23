from scipy.constants import physical_constants

hc_in_eV_and_Angstrom: float = (
    physical_constants["speed of light in vacuum"][0]
    * physical_constants["Planck constant in eV/Hz"][0]
    * 1e10  # Angstroms per metre
)


def interconvert_eV_Angstrom(wavelength_or_energy: float) -> float:
    return hc_in_eV_and_Angstrom / wavelength_or_energy


def convert_eV_to_angstrom(hv: float) -> float:
    return interconvert_eV_Angstrom(hv)


def convert_angstrom_to_eV(wavelength: float) -> float:
    return interconvert_eV_Angstrom(wavelength)
