"""Dataset ingestion orchestration: canonical dataset codes in, refreshed
PostgreSQL rows out, using the pieces that already exist.

    resolve_datasets       request form + catalog + ingestibility, no I/O
    fetch_and_normalize    one source fetch per distinct (organization, key),
                           normalize per dataset
    ingest_datasets        the above, then ONE transaction replacing every
                           requested dataset, then commit

Only the explicitly listed datasets are ingestible (:data:`SUPPORTED_DATASETS`).
Every other catalog dataset raises ``NotIngestibleError``: known to
metadata, no ingestion path yet. A dataset in :data:`UNAVAILABLE_SOURCES`
raises its subclass ``SourceUnavailableError`` with the recorded reason: its
legacy source is gone and no replacement is approved, so its historical
parity is held on a committed fixture but nothing can be fetched live.

Sources. Each organization with an ingestion path has one entry in
:data:`SOURCES`: how to derive the unit of fetching from a dataset's
metadata (an SDG indicator, a FAOSTAT domain, an EPI edition archive, the
WID bulk archive, a World Bank indicator, an ILO SDMX request, an IEA or UIS indicator, a Tax Foundation edition file), how
to fetch it from a client, how to normalize fetched rows for one dataset,
and how to open a default client. Datasets sharing a fetch key share one
download. This is a literal mapping, not a plugin mechanism.

A dataset listed in ``sspi.ingestion.derived.DERIVATIONS`` is computed from
another canonical dataset: its base is fetched and normalized, then the
registered transform runs. The base is written only if it was requested.

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

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sspi.errors import IngestionRequestError, NotIngestibleError, SourceUnavailableError
from sspi.ingestion import epi, fao, iea, ilo, taxfoundation, uis, wid, worldbank
from sspi.ingestion.derived import DERIVATIONS
from sspi.ingestion.epi import EPIClient, normalize_epi_dataset
from sspi.ingestion.fao import FAOBulkClient, normalize_fao_dataset
from sspi.ingestion.ilo import ILOClient, normalize_ilo_dataset
from sspi.ingestion.results import NormalizationResult
from sspi.ingestion.taxfoundation import TaxFoundationClient, normalize_taxfoundation_dataset
from sspi.ingestion.iea import IEAClient, normalize_iea_dataset
from sspi.ingestion.uis import UISClient, normalize_uis_dataset
from sspi.ingestion.unsdg import UNSDGClient, normalize_unsdg_dataset
from sspi.ingestion.wid import WIDClient, normalize_wid_dataset
from sspi.ingestion.worldbank import WorldBankClient, normalize_worldbank_dataset
from sspi.metadata import DatasetMetadata, MetadataCatalog

SUPPORTED_DATASETS: tuple[str, ...] = (
    # BIODIV
    "UNSDG_MARINE",
    "UNSDG_TERRST",
    "UNSDG_FRSHWT",
    # REDLST
    "UNSDG_REDLST",
    # CHMPOL
    "UNSDG_STKHLM",
    "UNSDG_MINMAT",
    "UNSDG_MONTRL",
    "UNSDG_BASELA",
    "UNSDG_ROTDAM",
    # WATMAN
    "UNSDG_WTSTRS",
    "UNSDG_WUSEFF",
    "UNSDG_CWUEFF",
    # NITROG
    "EPI_NITROG",
    # DEFRST
    "UNFAO_FRSTLV",
    "UNFAO_FRSTAV",
    # CARBON
    "UNFAO_CRBNLV",
    "UNFAO_CRBNAV",
    # ISHRAT
    "WID_NINCSH_PRETAX_P90P100",
    "WID_NINCSH_PRETAX_P0P50",
    # GINIPT
    "WB_GINIPT",
    # EMPLOY
    "ILO_EMPLOY_TO_POP",
    # COLBAR
    "ILO_COLBAR",
    # ALTNRG
    "IEA_TLCOAL",
    "IEA_NATGAS",
    "IEA_NCLEAR",
    "IEA_HYDROP",
    "IEA_GEOPWR",
    "IEA_BIOWAS",
    "IEA_FSLOIL",
    # NRGINT
    "UNSDG_NRGINT",
    # AIRPOL
    "UNSDG_AIRPOL",
    # BEEFMK
    "UNFAO_BFPROD",
    "UNFAO_BFCONS",
    "WB_POPULN",  # also GTRANS
    # COALPW: the seven ALTNRG datasets
    # GTRANS
    "IEA_TCO2EM",
    # PUPTCH
    "WB_PUPTCH",
    # ENRPRI
    "UIS_ENRPRI",
    # ENRSEC
    "UIS_ENRSEC",
    # YRSEDU
    "UIS_YRSEDU",
    # TAXREV
    "WB_TAXREV",
    # TXRDST: the two pre-tax shares above (ISHRAT) and
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50",
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100",
    # CRPTAX
    "TF_CRPTAX",
)

# Datasets with committed historical parity evidence whose legacy source can no longer be fetched and for which no
# replacement source is approved: dataset code -> why. Never in SUPPORTED_DATASETS.
UNAVAILABLE_SOURCES: dict[str, str] = {
    # MSWGEN
    "EPI_MSWGEN": (
        "the legacy source, series WPC of the 2024 EPI indicator archive (epi2024indicators.zip), is no longer served "
        "and the current EPI edition (2026) publishes no WPC series; no replacement source is approved. Historical parity "
        "is held on the committed 2024 fixture (see docs/indicator-migration.md and MSWGEN-1)"
    ),
}


@dataclass(frozen=True, slots=True)
class Source:
    """One organization's ingestion path."""

    organization_code: str
    fetch_key: Callable[[DatasetMetadata], str]  # what one fetch covers, from canonical metadata
    fetch: Callable[[Any, str], Any]  # (client, key) -> raw rows
    normalize: Callable[[DatasetMetadata, Any], NormalizationResult]
    open_client: Callable[[], Any]


SOURCES: dict[str, Source] = {
    "UNSDG": Source("UNSDG", lambda d: d.source.query_code, lambda client, key: client.fetch_indicator(key), normalize_unsdg_dataset, lambda: UNSDGClient()),
    "UNFAO": Source("UNFAO", lambda d: fao.source_filters(d).domain, lambda client, key: client.fetch_domain(key), normalize_fao_dataset, lambda: FAOBulkClient()),
    "EPI": Source("EPI", lambda d: epi.archive_key(d), lambda client, key: client.fetch_archive(key), normalize_epi_dataset, lambda: EPIClient()),
    "WID": Source("WID", lambda d: wid.archive_key(d), lambda client, key: client.fetch_archive(key), normalize_wid_dataset, lambda: WIDClient()),
    "WB": Source("WB", lambda d: worldbank.indicator_key(d), lambda client, key: client.fetch_indicator(key), normalize_worldbank_dataset, lambda: WorldBankClient()),
    "ILO": Source("ILO", lambda d: ilo.query_key(d), lambda client, key: client.fetch_query(key), normalize_ilo_dataset, lambda: ILOClient()),
    "IEA": Source("IEA", lambda d: iea.indicator_key(d), lambda client, key: client.fetch_indicator(key), normalize_iea_dataset, lambda: IEAClient()),
    "UIS": Source("UIS", lambda d: uis.indicator_key(d), lambda client, key: client.fetch_indicator(key), normalize_uis_dataset, lambda: UISClient()),
    "TF": Source("TF", lambda d: taxfoundation.file_key(d), lambda client, key: client.fetch_file(key), normalize_taxfoundation_dataset, lambda: TaxFoundationClient()),
}


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
    source_fetches: tuple[str, ...]  # distinct fetch keys fetched, in order (SDG indicator, FAOSTAT domain, EPI or WID archive, World Bank indicator, ILO query, IEA or UIS indicator)

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
        if code in UNAVAILABLE_SOURCES:
            raise SourceUnavailableError(f"{code} cannot be ingested: {UNAVAILABLE_SOURCES[code]}")
        if code not in SUPPORTED_DATASETS or dataset.source.organization_code not in SOURCES:
            raise NotIngestibleError(
                f"{code} is defined in the metadata catalog (organization {dataset.source.organization_code}) but has no ingestion path yet; "
                f"ingestible datasets today: {list(SUPPORTED_DATASETS)}"
            )
        datasets.append(dataset)
    return tuple(datasets)


def _base_dataset(dataset: DatasetMetadata, metadata: MetadataCatalog) -> DatasetMetadata:
    """The dataset whose source rows are normalized for ``dataset``: itself,
    or its registered derivation base."""
    derivation = DERIVATIONS.get(dataset.code)
    if derivation is None:
        return dataset
    base = metadata.dataset(derivation.base)
    if not isinstance(base, DatasetMetadata):
        raise NotIngestibleError(f"{dataset.code} is derived from {derivation.base}, which has no complete definition")
    if (
        base.source.organization_code != dataset.source.organization_code
        or base.source.query_code != dataset.source.query_code
        or base.source.organization_series_code != dataset.source.organization_series_code
    ):
        raise NotIngestibleError(
            f"{dataset.code} is derived from {derivation.base} but their canonical sources disagree "
            f"({dataset.source.organization_code}:{dataset.source.query_code!r}/{dataset.source.organization_series_code!r} vs "
            f"{base.source.organization_code}:{base.source.query_code!r}/{base.source.organization_series_code!r})"
        )
    return base


def _client_for(clients: Any, organization_code: str) -> Any:
    """``clients`` is one client used for every organization, or a mapping by organization code."""
    if isinstance(clients, Mapping):
        try:
            return clients[organization_code]
        except KeyError:
            raise IngestionRequestError(f"no source client supplied for organization {organization_code!r}") from None
    return clients


def fetch_and_normalize(
    datasets: tuple[DatasetMetadata, ...], clients: Any, *, metadata: MetadataCatalog
) -> tuple[list[tuple[DatasetMetadata, NormalizationResult]], tuple[str, ...]]:
    """Fetch each distinct (organization, key) once, in first-appearance
    order, and normalize every dataset from its fetch; a derived dataset is
    normalized as its base and then transformed. Returns the per-dataset
    results in request order and the fetch keys fetched."""
    bases = {dataset.code: _base_dataset(dataset, metadata) for dataset in datasets}
    fetches: dict[tuple[str, str], None] = {}
    for dataset in datasets:
        base = bases[dataset.code]
        fetches.setdefault((base.source.organization_code, SOURCES[base.source.organization_code].fetch_key(base)))
    rows_by_fetch = {
        (organization, key): SOURCES[organization].fetch(_client_for(clients, organization), key) for organization, key in fetches
    }
    normalized: list[tuple[DatasetMetadata, NormalizationResult]] = []
    for dataset in datasets:
        base = bases[dataset.code]
        source = SOURCES[base.source.organization_code]
        result = source.normalize(base, rows_by_fetch[(base.source.organization_code, source.fetch_key(base))])
        if base is not dataset:
            result = NormalizationResult(DERIVATIONS[dataset.code].transform(dataset, result.observations), result.skipped_areas, result.missing_values)
        normalized.append((dataset, result))
    return normalized, tuple(key for _, key in fetches)


def ingest_datasets(codes: Any, database: Any, *, metadata: MetadataCatalog | None = None, client: Any | None = None) -> IngestionRun:
    """Refresh the requested datasets from their source into PostgreSQL.

    ``client`` may be injected (tests, programmatic use): one object used for
    every organization in the request, or a mapping by organization code.
    Otherwise one default client per organization needed is created for this
    call and closed afterwards. An injected client is never closed.
    """
    from sspi.db import Repository  # persistence stays out of the module graph until needed

    catalog = MetadataCatalog.load() if metadata is None else metadata
    datasets = resolve_datasets(codes, catalog)

    owned: dict[str, Any] = {}
    try:
        if client is None:
            for dataset in datasets:
                organization = _base_dataset(dataset, catalog).source.organization_code
                if organization not in owned:
                    owned[organization] = SOURCES[organization].open_client()
        normalized, fetches = fetch_and_normalize(datasets, owned if client is None else client, metadata=catalog)
    finally:
        for source in owned.values():
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
