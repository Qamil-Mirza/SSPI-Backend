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


class DatabaseConfigurationError(SSPIError):
    """No usable database configuration was found where one was required."""


class InvalidScoreError(SSPIError, ValueError):
    """An IndicatorScore cannot be persisted as it stands.

    Raised for a score that is not a number or ``None`` (a tuple, a string, a
    bool), a non-finite number, a number outside [0, 1], a non-string unit, a
    computed input that cannot be stored, or two scores sharing one identity
    in a single write. Nothing is normalised; the caller must decide.
    """


class IngestionError(SSPIError):
    """Base class for failures while fetching or normalizing source data."""


class SourceRequestError(IngestionError):
    """The external source could not be reached or answered with an error status."""


class SourceResponseError(IngestionError):
    """The external source answered, but not with a usable payload."""


class NormalizationError(IngestionError, ValueError):
    """A source record cannot be turned into a canonical Observation."""


class DuplicateObservationError(NormalizationError):
    """Two source records map to the same (dataset_code, country_code, year).

    Nothing is chosen; the caller must pin the distinguishing dimension or
    give each slice its own dataset code.
    """


class InvalidObservationError(SSPIError, ValueError):
    """An observation violates an invariant the scoring kernel relies on.

    Raised for a missing or non-string identifier, a non-integer year, a
    non-finite value, or two observations sharing the same
    (dataset_code, country_code, year) identity. Domain rules such as
    country-code format or plausible year ranges are *not* enforced here;
    they belong to the ingestion boundary.
    """


class ImputationError(SSPIError, ValueError):
    """Imputation cannot proceed: empty reference data, inconsistent units,
    observations from the wrong dataset, or a duplicate identity in the
    input series. Mirrors the conditions the legacy helpers raised on."""


class IndicatorDefinitionError(MetadataError):
    """An executable indicator definition disagrees with the canonical
    metadata (different dataset dependencies) or with itself (its observed
    and imputed score functions take different parameters)."""


class ScoreIntegrityError(SSPIError):
    """A persisted indicator score is internally inconsistent: the stored
    ``imputed`` flag does not match the classification recomputed from the
    embedded inputs. The row was written outside the repository or altered."""


class InvalidQueryError(SSPIError, ValueError):
    """A query's arguments are malformed: both or neither of datasets and
    indicators, an empty code list, a bare string where a list was expected,
    a malformed country code or year range, or an option that does not apply
    to the query kind. Raised before any database access."""
