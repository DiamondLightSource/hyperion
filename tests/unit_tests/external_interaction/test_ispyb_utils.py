import re

import pytest

from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_visit_string_from_path,
)

TIME_FORMAT_REGEX = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


def test_get_current_time_string():
    current_time = get_current_time_string()

    assert isinstance(current_time, str)
    assert re.match(TIME_FORMAT_REGEX, current_time) is not None


@pytest.mark.parametrize(
    "visit_path, expected_match",
    [
        ("/dls/i03/data/2022/cm6477-45/", "cm6477-45"),
        ("/dls/i03/data/2022/cm6477-45", "cm6477-45"),
        ("/dls/i03/data/2022/mx54663-1/", "mx54663-1"),
        ("/dls/i03/data/2022/mx54663-1", "mx54663-1"),
        ("/dls/i03/data/2022/mx53-1/", None),
        ("/dls/i03/data/2022/mx53-1", None),
        ("/dls/i03/data/2022/mx5563-1565/", None),
        ("/dls/i03/data/2022/mx5563-1565", None),
    ],
)
def test_find_visit_in_visit_path(visit_path: str, expected_match: str):
    test_visit_path = get_visit_string_from_path(visit_path)
    assert test_visit_path == expected_match
