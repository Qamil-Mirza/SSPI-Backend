"""Dataset ingestion orchestration: canonical dataset codes in, refreshed
PostgreSQL rows out, using the pieces that already exist.

    resolve_datasets       request form + catalog + ingestibility, no I/O
    fetch_and_normalize    one source fetch per distinct query, normalize per dataset
    ingest_datasets        the above, then ONE transaction replacing every
                           requested dataset, then commit

Only the explicitly listed UN SDG datasets are ingestible today
(:data:`SUPPORTED_DATASETS`: the three BIODIV inputs and ``UNSDG_REDLST``).
Every other catalog dataset raises ``NotIngestibleError``: known to
metadata, no ingestion path yet. The other UNSDG entries carry the SDG
indicator number where a series code belongs, so the normalizer could not
select their rows even if they were allowed.

Sequence and atomicity. Validation happens before any network or database
use. All fetching and normalization happens with no transaction open, so a
source or normalization failure changes nothing in PostgreSQL. The writes
for the whole batch share one transaction: a failure part-way rolls every
requested dataset back, so a three-dataset BIODIV refresh is all or nothing.

Ingestion replaces observation rows only. It never runs an indicator,
imputes, or touches score rows; persisted scores may be stale until
``run_indicator`` is called again. That is deliberate and documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sspi.errors import IngestionRequestError, NotIngestibleError
from sspi.ingestion.unsdg import ORGANIZATION_CODE, NormalizationResult, UNSDGClient, normalize_unsdg_dataset
from sspi.metadata import DatasetMetadata, MetadataCatalog

SUPPORTED_DATASETS: tuple[str, ...] = ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT", "UNSDG_REDLST")


@dataclass(frozen=True, slots=True)
class DatasetIngestion:
    """What one dataset's refresh did: rows written and normalization diagnostics."""

    dataset_code: str
    source_query: str
    observations_written: int
    skipped_areas: tuple[tuple[str, str], ...]  # (source area code, name) with no ISO3 mapping, e.g. regional aggregates
    missing_values: int  # empty source values dropped, mapped areas only


@dataclass(frozen=True, slots=True)
class IngestionRun:
    """Result of one ``ingest_datasets`` call, in request order."""

    datasets: tuple[str, ...]
    per_dataset: tuple[DatasetIngestion, ...]
    source_fetches: tuple[str, ...]  # distinct source queries fetched, in order

    @property
    def observations_written(self) -> int:
        return sum(d.observations_written for d in self.per_dataset)

    @property
    def counts(self) -> dict[str, int]:
        return {d.dataset_code: d.observations_written for d in self.per_dataset}


def normalize_request(codes: Any) -> tuple[str, ...]:
    """A dataset code, or a list/tuple of codes, as a tuple in the given order.
    Other containers, empty requests, non-string entries and duplicates are
    rejected with ``IngestionRequestError``."""
    if isinstance(codes, str):
        request: tuple[Any, ...] = (codes,)
    elif isinstance(codes, (list, tuple)):
        request = tuple(codes)
    else:
        raise IngestionRequestError(f"dataset codes must be a string or a list/tuple of strings, got {type(codes).__name__}")
    if not request:
        raise IngestionRequestError("no dataset codes requested")
    for code in request:
        if not isinstance(code, str) or not code:
            raise IngestionRequestError(f"dataset codes must be non-empty strings, got {code!r}")
    duplicates = sorted({code for code in request if request.count(code) > 1})
    if duplicates:
        raise IngestionRequestError(f"duplicate dataset codes requested: {duplicates}")
    return request


def resolve_datasets(codes: Any, metadata: MetadataCatalog) -> tuple[DatasetMetadata, ...]:
    """Validate a request against the catalog and the ingestion allowlist.

    Unknown codes raise ``UnknownCodeError``; known datasets without an
    ingestion path raise ``NotIngestibleError``. No database or network use.
    """
    datasets: list[DatasetMetadata] = []
    for code in normalize_request(codes):
        dataset = metadata.dataset(code)
        if not isinstance(dataset, DatasetMetadata):
            raise NotIngestibleError(f"{code} is listed in the metadata catalog but has no complete definition; ingestible datasets today: {list(SUPPORTED_DATASETS)}")
        if dataset.source.organization_code != ORGANIZATION_CODE or code not in SUPPORTED_DATASETS:
            raise NotIngestibleError(
                f"{code} is defined in the metadata catalog (organization {dataset.source.organization_code}) but has no ingestion path yet; "
                f"ingestible datasets today: {list(SUPPORTED_DATASETS)}"
            )
        datasets.append(dataset)
    return tuple(datasets)


def fetch_and_normalize(datasets: tuple[DatasetMetadata, ...], client: Any) -> tuple[list[tuple[DatasetMetadata, NormalizationResult]], tuple[str, ...]]:
    """Fetch each distinct source query once, in first-appearance order, and
    normalize every dataset from its query's rows. Returns the per-dataset
    results in request order and the queries fetched."""
    queries: dict[str, list[DatasetMetadata]] = {}
    for dataset in datasets:
        queries.setdefault(dataset.source.query_code, []).append(dataset)
    rows_by_query = {query: client.fetch_indicator(query) for query in queries}
    normalized = [(dataset, normalize_unsdg_dataset(dataset, rows_by_query[dataset.source.query_code])) for dataset in datasets]
    return normalized, tuple(queries)


def ingest_datasets(codes: Any, database: Any, *, metadata: MetadataCatalog | None = None, client: Any | None = None) -> IngestionRun:
    """Refresh the requested datasets from their source into PostgreSQL.

    ``client`` may be injected (tests); otherwise a ``UNSDGClient`` is created
    for this call and closed afterwards. An injected client is never closed.
    """
    from sspi.db import Repository  # persistence stays out of the module graph until needed

    catalog = MetadataCatalog.load() if metadata is None else metadata
    datasets = resolve_datasets(codes, catalog)

    owns_client = client is None
    source = UNSDGClient() if owns_client else client
    try:
        normalized, fetches = fetch_and_normalize(datasets, source)
    finally:
        if owns_client:
            source.close()

    with database.transaction() as session:
        repo = Repository(session)
        per_dataset = tuple(
            DatasetIngestion(
                dataset_code=dataset.code,
                source_query=dataset.source.query_code,
                observations_written=repo.replace_dataset(dataset.code, result.observations),
                skipped_areas=result.skipped_areas,
                missing_values=result.missing_values,
            )
            for dataset, result in normalized
        )
    return IngestionRun(tuple(d.code for d in datasets), per_dataset, fetches)
