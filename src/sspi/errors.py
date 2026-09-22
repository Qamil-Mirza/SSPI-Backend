"""Exception types shared across the sspi package."""


class SSPIError(Exception):
    """Base class for every exception raised by the sspi package."""


class MetadataError(SSPIError):
    """The canonical metadata files are malformed or inconsistent.

    Raised once per load with every problem found, each prefixed by the file
    it came from, so a bad batch is fixed in one round trip.
    """


class UnknownCodeError(MetadataError, KeyError):
    """A catalog lookup used an indicator or dataset code that does not exist."""

    def __str__(self) -> str:  # KeyError would otherwise repr() the message
        return str(self.args[0]) if self.args else ""


class InvalidObservationError(SSPIError, ValueError):
    """An observation violates an invariant the scoring kernel relies on.

    Raised for a missing or non-string identifier, a non-integer year, a
    non-finite value, or two observations sharing the same
    (dataset_code, country_code, year) identity. Domain rules such as
    country-code format or plausible year ranges are *not* enforced here;
    they belong to the ingestion boundary.
    """
