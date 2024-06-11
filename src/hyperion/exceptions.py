from typing import Callable, Generator, Type, TypeVar

from bluesky.preprocessors import contingency_wrapper
from bluesky.utils import Msg


class WarningException(Exception):
    """An exception used when we want to warn GDA of a
    problem but continue with UDC anyway"""

    pass


T = TypeVar("T")


def catch_exception_and_warn(
    exception_to_catch: Type[Exception],
    func: Callable[..., Generator[Msg, None, T]],
    *args,
    **kwargs,
) -> Generator[Msg, None, T]:
    """A plan wrapper to catch a specific exception and instead raise a WarningException,
    so that UDC is not halted

    Example usage:

    'def plan_which_can_raise_exception_a(*args, **kwargs):
        ...
    yield from catch_exception_and_warn(ExceptionA, plan_which_can_raise_exception_a, **args, **kwargs)'

    This will catch ExceptionA raised by the plan and instead raise a WarningException
    """

    def warn_if_exception_matches(exception: Exception):
        if isinstance(exception, exception_to_catch):
            raise WarningException(str(exception))
        else:
            raise

    return (
        yield from contingency_wrapper(
            func(*args, **kwargs),
            except_plan=warn_if_exception_matches,
        )
    )
