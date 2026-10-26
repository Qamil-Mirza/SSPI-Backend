"""ITU Global Cybersecurity Index: pure normalizer for the SSPI's local
transcription of the published scores.

The ITU publishes the GCI as reports, not as a data series. The legacy SSPI
transcribed each edition's country scores by hand into one CSV file
(:mod:`sspi.ingestion.localfiles`, key ``gci-local-indicator-summary``):
``Country``, then a score column and a rank column per edition (``2014``,
``Globa Rank``, ``2017``, ``Global Rank``, ... ``2024``, ``Global Rank``)
and a trailing empty column. Editions 2014, 2017 and 2018 publish scores on
0-1, editions 2020 and 2024 on 0-100.

:func:`normalize_itu_dataset` reproduces the legacy cleaner exactly
(``clean_itu_data`` in ``api/datasource/itu.py`` and ``clean_itu_cybsec``
in ``api/core/datasets/itu/itu_cybsec.py``), whatever the file holds:

* the table is reindexed on the cleaner's column list (``Country``, each
  edition, ``Rank_<edition>``); the file's rank columns have other names,
  so the rank columns are empty and dropped, and the file's own rank
  columns are never read;
* the 2024 and 2020 columns are divided by 100; 2014, 2017 and 2018 are
  not (CYBSEC-2). Nothing else rescales a value;
* the editions are melted into rows, the edition is the year; a row with
  an empty cell is dropped and counted as missing, a published zero is kept;
* the country is the legacy name matcher's answer
  (:func:`sspi.ingestion.geo.legacy_country_code`), or, for the five
  spellings it cannot code, the approved correction below;
* the values pass through ``DataFrame.to_json``, as the legacy cleaner
  stored them, so each value has at most ten decimal places
  (``99.86 / 100`` is stored as ``0.9986``);
* the unit is the legacy literal ``Percentage``, which must be the dataset's
  canonical unit.

The legacy clean collection then refused the whole dataset for a country
the matcher could not turn into a code of three capital letters, for a
repeated country-year and for a value that is not a number. The
transcription has five such names, so legacy could never store it
(CYBSEC-1). The project owner approved, on 2026-10-25, one source-specific
representation correction: :data:`APPROVED_NAME_CORRECTIONS` gives those
five spellings the ISO 3166-1 codes they name. It applies only to a name
the legacy matcher returned unchanged, by its exact spelling in this
source; it changes no value, year, scale or score, and neither the
transcription nor the generic matcher. Each corrected observation records
the correction in its provenance. Any other name the matcher cannot code, a
repeated country-year and a value that is not a number are still errors,
naming every offending row.

Nothing here touches a database.
"""

from __future__ import annotations

import io
import json
import math
import re
from typing import Any

from sspi.errors import DuplicateObservationError, NormalizationError
from sspi.ingestion.geo import legacy_country_code
from sspi.ingestion.localfiles import LocalFile
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "ITU"
SERIES_CODE = "GCI"  # the legacy collector's OrganizationSeriesCode
EDITIONS = ("2014", "2017", "2018", "2020", "2024")
DIVIDED_BY_100 = ("2024", "2020")  # the legacy cleaner's order
LEGACY_COLUMNS = ("Country", "2014", "Rank_2014", "2017", "Rank_2017", "2018", "Rank_2018", "2020", "Rank_2020", "2024", "Rank_2024")
LEGACY_UNIT = "Percentage"
# Project-owner approval of 2026-10-25 (CYBSEC-1): the five transcription spellings the legacy matcher leaves
# unchanged, and the ISO 3166-1 alpha-3 identity each names (pycountry name in the comment). Exact spellings only.
APPROVED_NAME_CORRECTIONS: dict[str, str] = {
    "Cote d'Ivoire": "CIV",  # Côte d'Ivoire
    "Macedonia": "MKD",  # North Macedonia (the name until 2019)
    "Micronesia": "FSM",  # Micronesia, Federated States of
    "State of Palestine": "PSE",  # Palestine, State of
    "Vatican": "VAT",  # Holy See (Vatican City State)
}
CORRECTION_DECISION = "CYBSEC-1: approved source-specific name correction (project owner, 2026-10-25)"
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")


def file_key(dataset: Any) -> str:
    """The local file a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no ITU source file (query_code) in canonical metadata")
    if source.organization_series_code != SERIES_CODE:
        raise NormalizationError(f"{dataset.code}: series {source.organization_series_code!r} is not the GCI transcription ({SERIES_CODE!r})")
    return source.query_code


def legacy_records(content: bytes) -> tuple[list[dict[str, Any]], int]:
    """The cleaner's rows as the legacy cleaner stored them, each with the source cell it came from
    (``SourceValue``), and the number of rows dropped for an empty cell."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    try:
        table = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - any unreadable file is the same failure
        raise NormalizationError(f"ITU transcription is not a readable CSV file: {type(exc).__name__}: {exc}") from None
    absent = [c for c in ("Country", *EDITIONS) if c not in table.columns]
    if absent:
        raise NormalizationError(f"ITU transcription lacks columns {absent}; found {list(table.columns)}")
    frame = pd.DataFrame(table, columns=list(LEGACY_COLUMNS))
    published = frame.copy()
    for edition in DIVIDED_BY_100:
        frame[edition] = frame[edition] / 100
    ranks = [c for c in LEGACY_COLUMNS if c.startswith("Rank_")]

    def melt(wide: Any) -> Any:
        return wide.drop(ranks, axis=1).melt(id_vars=["Country"], value_vars=list(EDITIONS), var_name="Year", value_name="Value")

    melted, source_values = melt(frame), melt(published)["Value"]
    melted["Unit"] = LEGACY_UNIT
    melted["IndicatorCode"] = "CYBSEC"
    kept = melted.dropna().copy()
    kept["CountryCode"] = kept["Country"].apply(legacy_country_code)
    kept["Year"] = kept["Year"].astype(int)
    stored = json.loads(str(kept.to_json(orient="records")))
    for record, position in zip(stored, kept.index, strict=True):
        record["SourceValue"] = source_values.at[position]
    return stored, len(melted) - len(kept)


def normalize_itu_dataset(dataset: DatasetMetadata, file: LocalFile) -> NormalizationResult:
    """Canonical observations for one dataset from the local GCI transcription."""
    key = file_key(dataset)
    if file.key != key:
        raise NormalizationError(f"{dataset.code}: file {file.key!r} is not the dataset's {key!r}")
    if dataset.unit != LEGACY_UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit {dataset.unit!r} is not the legacy cleaner's {LEGACY_UNIT!r}")
    records, missing = legacy_records(file.content)
    where = f"{dataset.code} file {key!r}"
    corrected: set[str] = set()
    for record in records:
        if not (isinstance(record["CountryCode"], str) and _STORABLE_COUNTRY.match(record["CountryCode"])) and record["Country"] in APPROVED_NAME_CORRECTIONS:
            record["CountryCode"] = APPROVED_NAME_CORRECTIONS[record["Country"]]
            corrected.add(record["Country"])
    unmatched = sorted({r["Country"] for r in records if not (isinstance(r["CountryCode"], str) and _STORABLE_COUNTRY.match(r["CountryCode"]))})
    if unmatched:
        raise NormalizationError(
            f"{where}: the legacy name matcher gives no three-letter code for {unmatched} and no correction is approved for them; "
            "the legacy clean collection refused the whole dataset for such names (CountryCode must be 3 characters). "
            f"Approved corrections (CYBSEC-1) cover only {sorted(APPROVED_NAME_CORRECTIONS)}."
        )
    observations: list[Observation] = []
    seen: dict[tuple[str, int], str] = {}
    for record in records:
        country, year, value, name = record["CountryCode"], record["Year"], record["Value"], record["Country"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise NormalizationError(f"{where}: ({name!r}, {year}) value {value!r} is not a finite number (the legacy clean collection refused it too)")
        if (country, year) in seen:
            raise DuplicateObservationError(f"{dataset.code}: {name!r} and {seen[(country, year)]!r} are both {country} in edition {year}")
        seen[(country, year)] = name
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_file": file.key,
            "source_edition": file.source.edition,
            "source_origin": file.source.origin,
            "source_sha256": file.sha256,
            "source_country_name": name,
            "source_column": str(year),
            "source_value": repr(float(record["SourceValue"])),
            "divided_by_100": str(year) in DIVIDED_BY_100,
        }
        if name in corrected:
            provenance["country_code_correction"] = CORRECTION_DECISION
        observations.append(Observation(dataset.code, country, year, float(value), LEGACY_UNIT, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), missing)
