from __future__ import annotations

from hyperion.parameters.rotation import MultiRotationScan

TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def test_multi_rotation_scan_params(test_multi_rotation_params: MultiRotationScan):
    for scan in test_multi_rotation_params.single_rotation_scans:
        assert isinstance(scan.omega_start_deg, float)
