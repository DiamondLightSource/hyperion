from artemis.exceptions import WarningException


class ISPyBDepositionNotMade(Exception):
    """Raised when the ISPyB or Zocalo callbacks can't access ISPyB deposition numbers."""

    pass


class NoCentreFoundException(WarningException):
    """Error for if zocalo is unable to find the centre during a gridscan."""

    pass
