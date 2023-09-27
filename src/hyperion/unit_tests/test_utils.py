import pytest

from hyperion.utils.utils import convert_angstrom_to_eV, convert_eV_to_angstrom

test_wavelengths = [1.620709, 1.2398425, 0.9762539, 0.8265616, 0.68880138]
test_energies = [7650, 10000, 12700, 15000, 18000]


def test_ev_to_a_converter():
    for i in range(len(test_energies)):
        assert convert_eV_to_angstrom(test_energies[i]) == pytest.approx(
            test_wavelengths[i]
        )


def test_a_to_ev_converter():
    for i in range(len(test_wavelengths)):
        assert convert_angstrom_to_eV(test_wavelengths[i]) == pytest.approx(
            test_energies[i]
        )
