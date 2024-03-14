import io
from functools import partial
from unittest.mock import MagicMock, patch

import pin_versions
import pytest


@pytest.fixture
def patched_run_pip_freeze():
    with patch("pin_versions.run_pip_freeze") as run_pip_freeze:
        with open("test_data/pip_freeze.txt") as freeze_output:
            mock_process = MagicMock()
            run_pip_freeze.return_value = mock_process
            mock_process.stdout = freeze_output.read()
            mock_process.returncode = 0
        yield run_pip_freeze


@pytest.mark.parametrize(
    "input, expected",
    [
        ("", ("", None)),
        (
            "    pydantic<2.0 # See https://github.com/DiamondLightSource/hyperion/issues/774",
            (
                "    pydantic<2.0 ",
                " See https://github.com/DiamondLightSource/hyperion/issues/774",
            ),
        ),
    ],
)
def test_strip_comment(input, expected):
    assert pin_versions.strip_comment(input) == expected


@pytest.mark.parametrize(
    "input, expected",
    [
        ("dls-dodal", "dls-dodal"),
        ("dls_dodal", "dls-dodal"),
        ("dls.dodal", "dls-dodal"),
    ],
)
def test_normalize(input, expected):
    assert pin_versions.normalize(input) == expected


def test_unpin():
    with io.StringIO() as output_file:
        with open("test_data/setup.cfg") as input_file:
            pin_versions.process_files(
                input_file, output_file, pin_versions.unpin_versions
            )
        with open("test_data/setup.cfg.unpinned") as expected_file:
            assert output_file.getvalue() == expected_file.read()


@patch("pin_versions.stdout")
def test_write_commit_message(mock_stdout, patched_run_pip_freeze):
    installed_versions = pin_versions.fetch_pin_versions()
    pin_versions.write_commit_message(installed_versions)
    mock_stdout.write.assert_called_once_with(
        "Pin dependencies prior to release. Dodal 1.13.1, nexgen 0.8.4"
    )


def test_pin(patched_run_pip_freeze):
    installed_versions = pin_versions.fetch_pin_versions()
    with io.StringIO() as output_file:
        with open("test_data/setup.cfg.unpinned") as input_file:
            pin_versions.process_files(
                input_file,
                output_file,
                partial(pin_versions.update_setup_cfg_line, installed_versions),
            )

        with open("test_data/setup.cfg.pinned") as expected_file:
            assert output_file.getvalue() == expected_file.read()
