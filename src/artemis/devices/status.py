from typing import Any, TypeVar

from ophyd.status import SubscriptionStatus

T = TypeVar("T")


def await_value(subscribable: Any, expected_value: T) -> SubscriptionStatus:
    def value_is(value, **_):
        return value == expected_value

    return SubscriptionStatus(subscribable, value_is)
