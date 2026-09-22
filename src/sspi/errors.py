"""Exception types shared across the sspi package."""


class SSPIError(Exception):
    """Base class for every exception raised by the sspi package."""


class InvalidObservationError(SSPIError, ValueError):
    """An observation violates an invariant the scoring kernel relies on.

    Raised for a missing or non-string identifier, a non-integer year, a
    non-finite value, or two observations sharing the same
    (dataset_code, country_code, year) identity. Domain rules such as
    country-code format or plausible year ranges are *not* enforced here;
    they belong to the ingestion boundary.
    """
