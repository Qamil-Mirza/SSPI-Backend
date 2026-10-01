"""Researcher-facing entry point: ``from sspi import SSPI``.

``SSPI`` sits above the components already built and adds no domain logic:

* :meth:`SSPI.query` reads persisted observations or indicator scores through
  the repository and returns a tidy pandas DataFrame. It is read-only: it
  never runs an indicator, imputes, ingests or writes.
* :meth:`SSPI.ingest` refreshes canonical datasets from their source via
  ``sspi.ingestion.runner.ingest_datasets``. It replaces observation rows
  only and never recomputes scores.
* :meth:`SSPI.run` executes one registered indicator via
  ``sspi.indicators.run_indicator`` and persists its scores. Computation is
  always explicit, so scores may be stale after an ingest until ``run``.
* The metadata lookups delegate to ``MetadataCatalog`` and ``CountryCatalog``.

Everything is lazy: constructing ``SSPI()`` opens no connection, reads no
configuration and loads no catalog. The database is resolved on the first
call that needs one, from an injected ``Database``, a URL, or the standard
configuration (``DATABASE_URL``, then the project-root ``.env``), and a
missing configuration raises ``DatabaseConfigurationError`` at that call.

Ownership is explicit: a database the facade created (from nothing or from a
URL) is disposed by :meth:`SSPI.close`; an injected ``Database`` is the
caller's and is never disposed. No session outlives a single call.

pandas lives here and only here; scoring, imputation and the repository keep
working on domain objects.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from sspi.config import USE_DEFAULT_ENV_FILE
from sspi.db import Database, Repository
from sspi.errors import InvalidQueryError
from sspi.imputation import is_imputed
from sspi.indicators import IndicatorRun, registry, run_indicator
from sspi.ingestion.runner import IngestionRun, ingest_datasets, resolve_datasets
from sspi.metadata import Country, CountryCatalog, CountryGroup, DatasetMetadata, IndicatorMetadata, MetadataCatalog, UnresolvedDataset
from sspi.scoring import IndicatorScore, Observation

__all__ = ["DATASET_DTYPES", "INDICATOR_DTYPES", "QuerySpec", "SSPI", "observations_frame", "scores_frame", "validate_query"]

# Stable schemas. Empty and populated frames share them exactly.
DATASET_DTYPES: dict[str, str] = {"dataset_code": "string", "country_code": "string", "year": "int64", "value": "float64", "unit": "string"}
INDICATOR_DTYPES: dict[str, str] = {"indicator_code": "string", "country_code": "string", "year": "int64", "score": "float64", "unit": "string", "imputed": "bool"}
PROVENANCE_COLUMN = "provenance"
INPUTS_COLUMN = "inputs"

_ISO3 = re.compile(r"^[A-Z]{3}$")
YearRange = tuple[int, int]


# --------------------------------------------------------------------------- #
# DataFrame builders (pure)
# --------------------------------------------------------------------------- #


def _frame(columns: dict[str, str], records: dict[str, list[Any]], *extras: tuple[str, list[Any]] | None) -> pd.DataFrame:
    data = {name: pd.array(records[name], dtype=dtype) for name, dtype in columns.items()}
    present = [e for e in extras if e is not None]
    for name, values in present:
        data[name] = pd.Series(values, dtype="object")
    return pd.DataFrame(data, columns=[*columns, *(name for name, _ in present)])


def observations_frame(observations: Iterable[Observation], include_provenance: bool = False) -> pd.DataFrame:
    """Tidy frame of observations in the order given. ``include_provenance``
    adds one object column holding each observation's provenance as a dict."""
    rows = list(observations)
    records = {
        "dataset_code": [o.dataset_code for o in rows],
        "country_code": [o.country_code for o in rows],
        "year": [o.year for o in rows],
        "value": [o.value for o in rows],
        "unit": [o.unit for o in rows],
    }
    extra = (PROVENANCE_COLUMN, [dict(o.provenance) for o in rows]) if include_provenance else None
    return _frame(DATASET_DTYPES, records, extra)


def _input_summary(o: Observation) -> dict[str, Any]:
    return {
        "dataset_code": o.dataset_code,
        "value": o.value,
        "unit": o.unit,
        "imputed": bool(o.provenance.get("imputed", False)),
        "imputation_method": o.provenance.get("imputation_method"),
    }


def scores_frame(scores: Iterable[IndicatorScore], include_inputs: bool = False, include_provenance: bool = False) -> pd.DataFrame:
    """Tidy frame of indicator scores in the order given. ``imputed`` is the
    derived classification (score-level provenance or any imputed input). A
    ``None`` score is NaN. ``include_inputs`` adds one object column holding
    a tuple of small dicts describing each score's inputs;
    ``include_provenance`` adds one object column holding each score's own
    derivation record as a dict (``{}`` for a directly computed score)."""
    rows = list(scores)
    records = {
        "indicator_code": [s.indicator_code for s in rows],
        "country_code": [s.country_code for s in rows],
        "year": [s.year for s in rows],
        "score": [float("nan") if s.score is None else s.score for s in rows],
        "unit": [s.unit for s in rows],
        "imputed": [is_imputed(s) for s in rows],
    }
    inputs = (INPUTS_COLUMN, [tuple(_input_summary(o) for o in s.inputs) for s in rows]) if include_inputs else None
    provenance = (PROVENANCE_COLUMN, [dict(s.provenance) for s in rows]) if include_provenance else None
    return _frame(INDICATOR_DTYPES, records, inputs, provenance)


# --------------------------------------------------------------------------- #
# Query validation (pure)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """A validated query: exactly one of ``datasets`` / ``indicators`` is set."""

    datasets: tuple[str, ...] | None
    indicators: tuple[str, ...] | None
    countries: tuple[str, ...] | None
    years: YearRange | None
    include_provenance: bool = False
    include_inputs: bool = False


def _code_list(name: str, value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raise InvalidQueryError(f"{name} must be a list of codes, not the string {value!r}")
    try:
        codes = tuple(value)
    except TypeError:
        raise InvalidQueryError(f"{name} must be a list of codes, got {value!r}") from None
    if not codes:
        raise InvalidQueryError(f"{name}=[] selects nothing; pass None for no restriction or at least one code")
    for code in codes:
        if not isinstance(code, str):
            raise InvalidQueryError(f"{name} entries must be strings, got {code!r}")
    return codes


def _years(value: Any) -> YearRange | None:
    if value is None:
        return None
    try:
        start, end = value
    except (TypeError, ValueError):
        raise InvalidQueryError(f"years must be an inclusive (start, end) pair, got {value!r}") from None
    for bound in (start, end):
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise InvalidQueryError(f"years must be integers, got {value!r}")
    if start > end:
        raise InvalidQueryError(f"years start must not exceed end, got {value!r}")
    return (start, end)


def validate_query(
    metadata: MetadataCatalog,
    *,
    datasets: Iterable[str] | None = None,
    indicators: Iterable[str] | None = None,
    countries: Iterable[str] | None = None,
    years: Any = None,
    include_provenance: bool = False,
    include_inputs: bool = False,
) -> QuerySpec:
    """Check and normalize query arguments before any database access.

    Dataset and indicator codes are validated against the catalog (unknown
    codes raise ``UnknownCodeError``). Country codes are validated for ISO3
    format only: the canonical persistence universe is wider than the
    country catalog (legacy sources emit e.g. ``XKX`` for Kosovo), so a
    well-formed code with no rows yields an empty frame rather than an error.
    Empty lists fail fast; ``None`` means unrestricted.
    """
    if (datasets is None) == (indicators is None):
        raise InvalidQueryError("pass exactly one of datasets=[...] or indicators=[...]")
    dataset_codes = _code_list("datasets", datasets)
    indicator_codes = _code_list("indicators", indicators)
    country_codes = _code_list("countries", countries)
    for code in dataset_codes or ():
        metadata.dataset(code)
    for code in indicator_codes or ():
        metadata.indicator(code)
    for code in country_codes or ():
        if not _ISO3.match(code):
            raise InvalidQueryError(f"countries entries must be ISO 3166-1 alpha-3 codes (three uppercase letters), got {code!r}")
    if dataset_codes is not None and include_inputs:
        raise InvalidQueryError("include_inputs applies to indicator queries only")
    return QuerySpec(dataset_codes, indicator_codes, country_codes, _years(years), include_provenance, include_inputs)


# --------------------------------------------------------------------------- #
# The facade
# --------------------------------------------------------------------------- #


class SSPI:
    """Notebook entry point to persisted SSPI data and explicit computation.

    ``database`` may be omitted (resolved from configuration on first use,
    owned by the facade), a URL string (owned by the facade), or an existing
    ``Database`` (owned by the caller, never disposed here). ``env_file``
    is forwarded to configuration loading; ``None`` disables the dotenv
    fallback.
    """

    def __init__(self, database: Database | str | None = None, *, env_file: str | Path | None | object = USE_DEFAULT_ENV_FILE) -> None:
        if database is None:
            self._database: Database | None = None
            self._owns_database = True
        elif isinstance(database, str):
            self._database = Database(database)
            self._owns_database = True
        elif isinstance(database, Database):
            self._database = database
            self._owns_database = False
        else:
            raise TypeError(f"database must be a Database, a URL string or None, got {type(database).__name__}")
        self._env_file = env_file
        self._metadata: MetadataCatalog | None = None
        self._countries: CountryCatalog | None = None
        self._closed = False

    # --- resources ------------------------------------------------------------

    @property
    def database(self) -> Database:
        """The underlying database, resolved from configuration on first access."""
        if self._closed:
            raise RuntimeError("this SSPI instance is closed")
        if self._database is None:
            self._database = Database.from_settings(env_file=self._env_file)
        return self._database

    @property
    def owns_database(self) -> bool:
        return self._owns_database

    @property
    def metadata(self) -> MetadataCatalog:
        if self._metadata is None:
            self._metadata = MetadataCatalog.load()
        return self._metadata

    @property
    def countries(self) -> CountryCatalog:
        if self._countries is None:
            self._countries = CountryCatalog.load()
        return self._countries

    def close(self) -> None:
        """Dispose the database if this facade created it. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._owns_database and self._database is not None:
            self._database.dispose()

    def __enter__(self) -> SSPI:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- querying (read-only) -------------------------------------------------

    def query(
        self,
        *,
        datasets: Iterable[str] | None = None,
        indicators: Iterable[str] | None = None,
        countries: Iterable[str] | None = None,
        years: YearRange | None = None,
        include_provenance: bool = False,
        include_inputs: bool = False,
    ) -> pd.DataFrame:
        """Persisted observations (``datasets=``) or indicator scores
        (``indicators=``) as a tidy DataFrame; exactly one of the two.

        Read-only: nothing is computed, imputed, ingested or written. Rows are
        ordered by code, country and year. A valid query with no rows returns
        an empty frame with the same columns and dtypes.
        """
        spec = validate_query(
            self.metadata,
            datasets=datasets,
            indicators=indicators,
            countries=countries,
            years=years,
            include_provenance=include_provenance,
            include_inputs=include_inputs,
        )
        with self.database.transaction() as session:
            repo = Repository(session)
            if spec.datasets is not None:
                rows = repo.get_observations(dataset_codes=spec.datasets, countries=spec.countries, years=spec.years)
                return observations_frame(rows, include_provenance=spec.include_provenance)
            scores = repo.get_scores(indicator_codes=spec.indicators, countries=spec.countries, years=spec.years)
            return scores_frame(scores, include_inputs=spec.include_inputs, include_provenance=spec.include_provenance)

    # --- ingestion (explicit) -----------------------------------------------------

    def ingest(self, datasets: str | list[str] | tuple[str, ...], *, client: Any | None = None) -> IngestionRun:
        """Refresh one or more canonical datasets from their source into
        PostgreSQL, replacing each dataset's stored series in one transaction.

        Validation (unknown code, dataset without an ingestion path, bad
        request form) happens before any database or network use. Nothing
        downstream is recomputed: persisted indicator scores that depend on
        these datasets stay as they are until :meth:`run`. ``client`` is for
        tests and programmatic use; by default a source client is created for
        the call and closed afterwards.
        """
        resolve_datasets(datasets, self.metadata)  # fail before resolving a database
        return ingest_datasets(datasets, self.database, metadata=self.metadata, client=client)

    # --- computation (explicit) -------------------------------------------------

    def run(self, indicator_code: str) -> IndicatorRun:
        """Execute one registered indicator on the observations currently in
        PostgreSQL and persist its observed and imputed scores. Delegates to
        ``sspi.indicators.run_indicator``; raises ``UnknownCodeError`` for an
        indicator with no executable definition."""
        registry.get(indicator_code)  # fail before touching the database
        return run_indicator(indicator_code, self.database, metadata=self.metadata, countries=self.countries)

    def executable_indicators(self) -> tuple[str, ...]:
        """Indicator codes that :meth:`run` can execute today."""
        return registry.codes()

    # --- metadata conveniences ---------------------------------------------------

    def indicator(self, code: str) -> IndicatorMetadata:
        return self.metadata.indicator(code)

    def dataset(self, code: str) -> DatasetMetadata | UnresolvedDataset:
        return self.metadata.dataset(code)

    def country(self, code: str) -> Country:
        return self.countries.country(code)

    def country_group(self, code: str) -> CountryGroup:
        return self.countries.group(code)
