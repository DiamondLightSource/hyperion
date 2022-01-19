from ophyd import Component, EpicsSignal


def epics_signal_put_wait(pv_name: str, wait: str = 1.0) -> EpicsSignal:
    """Creates a `Component` around an `EpicsSignal` that waits for a callback on a put.

    Args:
        pv_name (str): The name of the PV for the `EpicsSignal`
        wait (str, optional): The timeout to wait for a callback. Defaults to 1.0.

    Returns:
        EpicsSignal: An EpicsSignal that will wait for a callback.
    """
    return Component(EpicsSignal, pv_name, put_complete=True, write_timeout=wait)
