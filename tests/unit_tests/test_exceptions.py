import pytest
from bluesky.plan_stubs import null

from hyperion.exceptions import WarningException, catch_exception_and_warn


class _TestException(Exception):
    pass


def dummy_plan():
    yield from null()
    raise _TestException


def test_catch_exception_and_warn_correctly_raises_warning_exception(RE):
    with pytest.raises(WarningException):
        RE(catch_exception_and_warn(_TestException, dummy_plan))


def test_catch_exception_and_warn_correctly_raises_original_exception(RE):
    with pytest.raises(_TestException):
        RE(catch_exception_and_warn(ValueError, dummy_plan))
