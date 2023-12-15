from unittest.mock import MagicMock, patch

from hyperion.utils.get_run_number import (
    _find_next_run_number_from_files,
    get_run_number,
)


def test_find_next_run_number_from_files_gets_correct_number():
    assert (
        _find_next_run_number_from_files(
            ["V31-1-x0093_1.nxs", "V31-1-x0093_2.nxs", "V31-1-x0093_265.nxs"]
        )
        == 266
    )


@patch("hyperion.log.LOGGER.warning")
def test_find_next_run_number_gives_warning_with_wrong_nexus_names(
    mock_logger: MagicMock,
):
    assert (
        _find_next_run_number_from_files(
            ["V31-1-x0093.nxs", "eggs", "V31-1-x0093_1.nxs"]
        )
        == 2
    )
    assert mock_logger.call_count == 2


@patch("os.listdir")
@patch("hyperion.utils.get_run_number._find_next_run_number_from_files")
def test_get_run_number_finds_all_nexus_files(
    mock_find_next_run_number: MagicMock, mock_list_dir: MagicMock
):
    files = ["blah.nxs", "foo", "bar.nxs", "ham.h5"]
    mock_list_dir.return_value = files
    get_run_number("dir")
    mock_find_next_run_number.assert_called_once_with(["blah.nxs", "bar.nxs"])


@patch("os.listdir")
def test_if_nexus_files_are_unnumbered_then_return_one(
    mock_list_dir: MagicMock,
):
    assert _find_next_run_number_from_files(["file.nxs", "foo.nxs", "ham.nxs"]) == 1


@patch("os.listdir")
@patch("hyperion.utils.get_run_number._find_next_run_number_from_files")
def test_run_number_1_given_on_first_nexus_file(
    mock_find_next_run_number: MagicMock, mock_list_dir: MagicMock
):
    files = ["blah", "foo", "bar"]
    mock_list_dir.return_value = files
    assert get_run_number("dir") == 1
    mock_find_next_run_number.assert_not_called()
