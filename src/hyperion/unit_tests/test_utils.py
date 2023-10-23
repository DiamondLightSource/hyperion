import pytest

from hyperion.utils.utils import convert_angstrom_to_eV, convert_eV_to_angstrom

test_wavelengths = [1.620709, 1.2398425, 0.9762539, 0.8265616, 0.68880138]
test_energies = [7650, 10000, 12700, 15000, 18000]


@pytest.mark.parametrize(
    "test_wavelength, test_energy", list(zip(test_wavelengths, test_energies))
)
def test_ev_to_a_converter(test_wavelength, test_energy):
    assert convert_eV_to_angstrom(test_energy) == pytest.approx(test_wavelength)


@pytest.mark.parametrize(
    "test_wavelength, test_energy", list(zip(test_wavelengths, test_energies))
)
def test_a_to_ev_converter(test_wavelength, test_energy):
    assert convert_angstrom_to_eV(test_wavelength) == pytest.approx(test_energy)
