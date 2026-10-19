"""Generate the AQELEC golden files from a WEF workbook and a World Bank
response, with the pinned legacy code:

    wef_quelec_synthetic_cases.json, wb_avelec_cases.json, aqelec_synthetic_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_wef_cases.py [--real DIR]

By default the workbook is the committed synthetic one,
``tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx`` (invented data in the WEF
layout), and the World Bank response the committed sample
``tests/fixtures/wb/EG.ELC.ACCS.ZS_sample.json``; the golden files are
written next to this script.

``--real DIR`` reads the original WEF workbook ``DIR/WEF-GCIHH.xlsx`` and the
full World Bank response ``DIR/responses/EG.ELC.ACCS.ZS.json``, kept outside
the repository (docs/data-governance-review.md, GOV-2), and writes
``wef_quelec_cases.json``, ``wb_avelec_cases.json`` and ``aqelec_cases.json``
to ``DIR/golden``. Nothing from that directory is committed.

Everything recorded is the legacy code's own output:

* the legacy collector ``collect_wef_data`` runs with ``requests.get``
  answering with the workbook's bytes (status 200), and its raw insert is
  captured: the CSV text it made of the first sheet;
* the registered ``@dataset_cleaner`` for WEF_QUELEC reads that captured
  document, and its insert is checked with the legacy clean collection's own
  ``validate_documents_format`` before it is accepted, as in a legacy
  database;
* the WB_AVELEC cleaner runs on the World Bank rows the same way;
* the ``compute_aqelec`` view function runs unwrapped with its collection
  handles stubbed and the legacy insert validation applied.

The score function is a lambda inside the route; ``score_indicator`` is
wrapped to observe it, and it is evaluated on inputs no fixture holds (both
goalposts of both inputs, a zero access value). With the synthetic workbook
the four invalid variants of ``tests/fixtures/wef/build_synthetic.py`` are
also run through the collector and cleaner, recording how legacy failed.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import types
from datetime import datetime, timezone

from generate_education_cases import source_rows
from generate_inequality_cases import identities, observation_records, records, unwrap
from generate_legacy_cleaner_cases import RawStub
from legacy_stubs import MongoStub, legacy_skipped

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
SYNTHETIC_WORKBOOK = "tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx"
WB_SAMPLE = "tests/fixtures/wb/EG.ELC.ACCS.ZS_sample.json"
WEF_URL = "https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx"  # the legacy collector's literal
SERIES = "WEF.GCIHH.EOSQ064"
# (WB_AVELEC, WEF_QUELEC) handed to the legacy AQELEC lambda
SCORE_FUNCTION_CASES = (
    ("both at the lower goalposts", 0.0, 1.0),
    ("both at the upper goalposts", 100.0, 7.0),
    ("integer goalposts", 100, 7),
    ("half way on both", 50.0, 4.0),
    ("no access, best quality", 0.0, 7.0),
    ("full access, worst quality", 100.0, 1.0),
    ("fractional values", 98.9, 5.123456789012345),
)


def validating(name, legacy_collection, documents=()):
    class Validating(MongoStub):
        def insert_many(self, docs):
            legacy_collection.validate_documents_format(docs)
            return super().insert_many(docs)

    return Validating(name, documents)


def run_wef_legacy(content: bytes, metadata):
    """The legacy collector and cleaner on one workbook: (cleaned documents, captured raw CSV, requested URLs)."""
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.datasource import wef as wef_source
    from sspi_flask_app.models.database import sspi_clean_api_data

    requested, stored = [], []

    class Response:
        status_code = 200

        def __init__(self, body):
            self.content = body

    def get(url, *args, **kwargs):
        requested.append(url)
        return Response(content)

    class RawRecorder:
        def raw_insert_one(self, document, source_info, **kwargs):
            stored.append({"Raw": document, "Source": dict(source_info)})
            return 1

        def fetch_raw_data(self, source_info):
            return [dict(d) for d in stored]

    wef_source.requests = types.SimpleNamespace(get=get)
    wef_source.sspi_raw_api_data = RawRecorder()
    messages = list(wef_source.collect_wef_data(SERIES, username="golden"))
    assert requested == [WEF_URL] and len(stored) == 1, (requested, messages)
    module = importlib.import_module("sspi_flask_app.api.core.datasets.wef.wef_quelec")
    module.sspi_raw_api_data = wef_source.sspi_raw_api_data
    module.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)
    module.sspi_metadata = metadata
    return dataset_cleaner_registry["WEF_QUELEC"](), stored[0], requested


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", help="directory holding the original workbook and World Bank response (kept outside the repository)")
    args = parser.parse_args()
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.models.database import sspi_clean_api_data, sspi_incomplete_indicator_data, sspi_indicator_data

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = types.SimpleNamespace(get_source_info=lambda code: {"DatasetCode": code}, record_dataset_range=lambda documents, code: None)
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))
    if args.real:
        real = os.path.abspath(args.real)
        workbook_path, wb_path, out, suffix = os.path.join(real, "WEF-GCIHH.xlsx"), os.path.join(real, "responses", "EG.ELC.ACCS.ZS.json"), os.path.join(real, "golden"), ""
        workbook_name, wb_name = "WEF-GCIHH.xlsx (original, kept outside the repository)", "responses/EG.ELC.ACCS.ZS.json (full World Bank response, kept outside the repository)"
        os.makedirs(out, exist_ok=True)
    else:
        workbook_path, wb_path, out, suffix = os.path.join(NEW_REPO, SYNTHETIC_WORKBOOK), os.path.join(NEW_REPO, WB_SAMPLE), HERE, "_synthetic"
        workbook_name, wb_name = SYNTHETIC_WORKBOOK, WB_SAMPLE

    def generated_from(functions, fixtures):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            **({"fixture": fixtures[0]} if len(fixtures) == 1 else {"fixtures": list(fixtures)}),
        }

    def write(name, payload):
        with open(os.path.join(out, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    # ------------------------------------------------------------ WEF_QUELEC
    with open(workbook_path, "rb") as fh:
        content = fh.read()
    import hashlib

    wef_clean, raw, requested = run_wef_legacy(content, metadata)
    assert wef_clean and all(d["DatasetCode"] == "WEF_QUELEC" for d in wef_clean)
    import io

    import pandas as pd

    sheet = pd.read_csv(io.StringIO(raw["Raw"]["csv"]))
    selected = sheet[(sheet["Indicator ID"] == SERIES) & (sheet["Attribute 1"] == "Value")]
    year_columns = [c for c in sheet.columns if c.isdigit()]
    variants = []
    if not args.real:
        sys.path.insert(0, os.path.join(NEW_REPO, "tests", "fixtures", "wef"))
        import build_synthetic

        assert build_synthetic.cells(build_synthetic.build()) == build_synthetic.cells(content), "the committed synthetic workbook does not hold what build_synthetic.py writes"
        for name in build_synthetic.VARIANTS:
            try:
                cleaned, _, _ = run_wef_legacy(build_synthetic.build(name), metadata)
                variants.append({"name": name, "legacy_error": None, "observations": observation_records(cleaned)})
            except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
                variants.append({"name": name, "legacy_error": f"{type(exc).__name__}: {str(exc).splitlines()[0]}"})
    write(
        f"wef_quelec{suffix}_cases.json",
        {
            "generated_from": generated_from(
                [
                    "sspi_flask_app.api.datasource.wef.collect_wef_data (requests.get answered with the workbook bytes, raw insert captured)",
                    "sspi_flask_app.api.core.datasets.wef.wef_quelec.clean_wef_quelec (registered @dataset_cleaner, legacy clean-collection validation applied)",
                ],
                [workbook_name],
            ),
            "dataset_code": "WEF_QUELEC",
            "source_indicator": SERIES,
            "source_url": requested[0],
            "workbook_sha256": hashlib.sha256(content).hexdigest(),
            "workbook_bytes": len(content),
            "legacy_source_info": raw["Source"],
            "sheet_rows": len(sheet),
            "selected_rows": len(selected),
            "year_columns": year_columns,
            "observations": observation_records(wef_clean),
            "units": sorted({d["Unit"] for d in wef_clean}),
            "value_types": sorted({type(d["Value"]).__name__ for d in wef_clean}),
            "skipped_areas": [],
            "empty_source_values": int(selected[year_columns].isna().sum().sum()),
            "legacy_document_keys": sorted({k for d in wef_clean for k in d}),
            "invalid_variants": variants,
        },
    )
    years = [d["Year"] for d in wef_clean]
    print(f"WEF_QUELEC: {len(wef_clean)} observations, {len({d['CountryCode'] for d in wef_clean})} economies, {min(years)}-{max(years)}; variants: {[(v['name'], v['legacy_error']) for v in variants]}")

    # ------------------------------------------------------------ WB_AVELEC
    with open(wb_path, encoding="utf-8") as fh:
        wb_rows = json.load(fh)[1]
    module = importlib.import_module("sspi_flask_app.api.core.datasets.wb.wb_avelec")
    module.sspi_raw_api_data = RawStub(wb_rows)
    module.sspi_clean_api_data, module.sspi_metadata = validating("sspi_clean_api_data", sspi_clean_api_data), metadata
    wb_clean = dataset_cleaner_registry["WB_AVELEC"]()
    assert wb_clean and all(d["DatasetCode"] == "WB_AVELEC" for d in wb_clean)
    skipped, without_code, missing = legacy_skipped(wb_rows)
    write(
        "wb_avelec_cases.json",
        {
            "generated_from": generated_from(["sspi_flask_app.api.core.datasets.wb.wb_avelec.clean_wb_avelec (registered @dataset_cleaner, legacy clean-collection validation applied)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], [wb_name]),
            "dataset_code": "WB_AVELEC",
            "source_indicator": "EG.ELC.ACCS.ZS",
            "observations": observation_records(wb_clean),
            "skipped_areas": skipped,
            "rows_without_area_code": without_code,
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in wb_clean for k in d}),  # the cleaner pops Description
        },
    )
    print(f"WB_AVELEC: {len(wb_clean)} observations, {len({d['CountryCode'] for d in wb_clean})} countries")

    # ------------------------------------------------------------------- AQELEC
    captured = {}
    original = utilities.score_indicator

    def capturing(documents, indicator_code, score_function, unit, *rest, **kwargs):
        captured.setdefault(indicator_code, score_function)
        return original(documents, indicator_code, score_function, unit, *rest, **kwargs)

    module = importlib.import_module("sspi_flask_app.api.core.sspi.pg.inf.aqelec")
    module.app, module.parse_json, module.score_indicator = logger, (lambda value: value), capturing

    def compute(clean_documents):
        module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
        module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
        module.sspi_incomplete_indicator_data = validating("sspi_incomplete_indicator_data", sspi_incomplete_indicator_data)
        observed = unwrap(module.compute_aqelec)()
        return observed, module.sspi_incomplete_indicator_data.documents

    observed, incomplete = compute(wb_clean + wef_clean)
    empty_observed, _ = compute([])
    score_aqelec = captured["AQELEC"]
    (unit,) = {d["Unit"] for d in observed}
    write(
        f"aqelec{suffix}_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner functions for WB_AVELEC and WEF_QUELEC (WEF fed by the legacy collector)",
                    f"{module.__name__}.compute_aqelec (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                ],
                [wb_name, workbook_name],
            ),
            "indicator_code": "AQELEC",
            "formula": "0.5 * goalpost(WB_AVELEC, 0, 100) + 0.5 * goalpost(WEF_QUELEC, 1, 7)",
            "input_goalposts": {"WB_AVELEC": [0, 100], "WEF_QUELEC": [1, 7]},
            "score_function_parameters": list(score_aqelec.__code__.co_varnames[: score_aqelec.__code__.co_argcount]),
            "unit": unit,
            "impute_route_exists": hasattr(module, "impute_aqelec"),
            "observed_scores": records(observed, imputation=False),
            "incomplete_identities": identities(incomplete),
            "incomplete_groups": sorted(([d["CountryCode"], d["Year"], sorted(x["DatasetCode"] for x in d["Datasets"])] for d in incomplete), key=lambda r: (r[0], r[1])),
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
            "score_function_cases": [{"case": name, "inputs": {"WB_AVELEC": a, "WEF_QUELEC": q}, "score": score_aqelec(a, q)} for name, a, q in SCORE_FUNCTION_CASES],
        },
    )
    print(f"AQELEC: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {unit!r}), {len(incomplete)} incomplete; impute route: {hasattr(module, 'impute_aqelec')}")


if __name__ == "__main__":
    main()
