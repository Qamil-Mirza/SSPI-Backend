"""Generate the production-precedence fixture and goldens from a snapshot of the legacy production API.

Production (https://sspi.world) is the parity reference for the indicators in
``PRODUCTION_PRECEDENCE`` (tests/golden/parity.py): the project owner decided on
2026-11-09 that where the pinned legacy commit and production disagree,
production wins. This script reads a private snapshot of three public
production collections and writes:

* ``tests/fixtures/production/sspi_clean_api_data_<date>.json``: production's
  clean rows for the datasets those indicators read, verbatim and in the order
  production served them;
* ``tests/golden/production/<indicator>_production_cases.json``: production's
  own scores for each indicator: every observed score (``sspi_indicator_data``)
  and every score in the aggregation window (``sspi_item_data`` indicator rows,
  observed and imputed; a window score is imputed when it is not an observed
  score).

No legacy code runs here and nothing is recomputed: the goldens are production
output. The snapshot (fetched 2026-11-09, checksums in SHA256SUMS) is kept in
local-data/production/<date>/ and not committed; the committed subset is
reproducible from it byte for byte.

Usage:
    .venv/bin/python tests/golden/generate_production_cases.py [--snapshot local-data/production/2026-11-09]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT_DATE = "2026-11-09"
BASE_URL = "https://sspi.world/api/v1/query"
FETCHED_AT = {  # UTC, when each collection was downloaded (GET {BASE_URL}/<collection>, no parameters)
    "sspi_item_data": "2026-11-09T21:07:48Z",
    "sspi_indicator_data": "2026-11-09T21:07:48Z",
    "sspi_clean_api_data": "2026-11-09T21:20:00Z",
}
INDICATORS = {  # indicator -> the datasets its computation reads
    "BIODIV": ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"),
    "MSWGEN": ("EPI_MSWGEN",),
}
FIXTURE = REPO / "tests" / "fixtures" / "production" / f"sspi_clean_api_data_{SNAPSHOT_DATE}.json"
GOLDEN_DIR = REPO / "tests" / "golden" / "production"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=REPO / "local-data" / "production" / SNAPSHOT_DATE)
    args = parser.parse_args()
    files = {name: args.snapshot / f"{name}.json" for name in FETCHED_AT}
    snapshot = {
        "base_url": BASE_URL,
        "date": SNAPSHOT_DATE,
        "collections": {name: {"fetched_at": FETCHED_AT[name], "sha256": sha256(path)} for name, path in files.items()},
    }
    clean = json.loads(files["sspi_clean_api_data"].read_text(encoding="utf-8"))
    indicator_rows = json.loads(files["sspi_indicator_data"].read_text(encoding="utf-8"))
    item_rows = json.loads(files["sspi_item_data"].read_text(encoding="utf-8"))

    datasets = {code for codes in INDICATORS.values() for code in codes}
    rows = [row for row in clean if row["DatasetCode"] in datasets]
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)  # one row per line: verbatim records, reviewable diffs
    FIXTURE.write_text("[\n" + ",\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n]\n", encoding="utf-8")
    fixture = str(FIXTURE.relative_to(REPO))

    window_countries = sorted({r["CountryCode"] for r in item_rows})
    window_years = sorted({r["Year"] for r in item_rows})
    for code, dataset_codes in INDICATORS.items():
        observed = [
            {"country_code": r["CountryCode"], "year": r["Year"], "score": r["Score"], "unit": r["Unit"]}
            for r in indicator_rows if r["IndicatorCode"] == code
        ]
        observed_keys = {(r["country_code"], r["year"]) for r in observed}
        window = [
            {"country_code": r["CountryCode"], "year": r["Year"], "score": r["Score"], "imputed": (r["CountryCode"], r["Year"]) not in observed_keys}
            for r in item_rows if r["ItemType"] == "Indicator" and r["ItemCode"] == code
        ]
        write_json(GOLDEN_DIR / f"{code.lower()}_production_cases.json", {
            "generated_from": {"production": snapshot, "generator": "tests/golden/generate_production_cases.py"},
            "indicator_code": code,
            "dataset_codes": list(dataset_codes),
            "source_fixture": fixture,
            "source_fixture_sha256": sha256(FIXTURE),
            "window": {"countries": window_countries, "years": [window_years[0], window_years[-1]]},
            "observed_scores": observed,
            "window_scores": window,
        })
        print(f"{code}: {len(observed)} observed, {len(window)} window scores ({sum(w['imputed'] for w in window)} imputed)")
    print(f"fixture: {fixture} ({FIXTURE.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
