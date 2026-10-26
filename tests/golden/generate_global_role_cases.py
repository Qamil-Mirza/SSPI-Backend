"""Generate the Global Role golden files with the pinned legacy code:

    sipri_armexp_synthetic_cases.json, armexp_synthetic_cases.json
        from the committed synthetic answer tests/fixtures/sipri/armstransfers_synthetic.json
    sipri_armexp_corrected_synthetic_cases.json
        the same, with only the approved SIPRI_ARMEXP name table (ARMEXP-4) patched into the cleaner
    milexp_characterization_cases.json
        what the pinned MILEXP collector, cleaner and routes do with the synthetic
        tests/fixtures/sipri/milex_synthetic.json (MILEXP is not migrated)
    milexp_workbook_synthetic_cases.json
        SIPRI_MILEXP's approved source (MILEXP-4), the revised workbook, read here INDEPENDENTLY of the new
        backend (this is not legacy code: the legacy collector read the API) with the approved corrections
        (MILEXP-1, MILEXP-2), checked by the legacy clean collection's validation; then the pinned legacy
        compute and impute routes on those rows (legacy scoring on identical inputs), and the legacy cleaner's
        own divergence recorded from the characterization above
    rdfund_cases.json
        from the committed UN SDG samples tests/fixtures/unsdg/9_5_1_sample.json and 9_5_2_sample.json
        (their dataset files come from generate_unsdg_cases.py)
    foraid_characterization_cases.json
        what the pinned FORAID compute route does (FORAID is not migrated)

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \\
        /path/to/sspi-backend/tests/golden/generate_global_role_cases.py [--real DIR]

``--real DIR`` reads the original answers kept outside the repository
(``DIR/sipri/armexp_response_2026-10-26.json``, ``DIR/sipri/milexp_response_2026-10-26.json``,
``DIR/sipri/SIPRI-Milex-data-1949-2025_v1.2.xlsx``,
``DIR/unsdg/9.5.1_2026-10-26.json``, ``DIR/unsdg/9.5.2_2026-10-26.json``;
docs/data-governance-review.md, GOV-7) and writes ``DIR/sipri/golden/`` and
``DIR/unsdg/golden/``, never the repository.

Everything recorded is the legacy code's own output:

* ARMEXP and MILEXP: the registered ``@dataset_collector`` runs with
  ``requests.post`` answering with the fixture, its raw insert captured; the
  registered cleaner reads that document; its insert is checked by the
  legacy clean collection's ``validate_documents_format``. The compute and
  impute routes run unwrapped with collection handles replaced by
  ``MongoStub`` collections whose inserts first apply the legacy
  collections' own validation;
* RDFUND: the registered cleaners' ``extract_sdg`` + ``filter_sdg`` on the
  verbatim UN SDG rows, then ``compute_rdfund`` and ``impute_rdfund``;
* FORAID: ``compute_foraid`` with the legacy ``SSPIRawAPIData`` class over an
  in-memory collection.

Probes (an invented observed row for a hard-coded reference-class country,
an empty section) record how the legacy routes fail; they are not parity
evidence and are not committed sources.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import identities, observation_records, records, unwrap
from generate_public_safety_cases import (
    RawCapture,
    builder,
    conflicts_of,
    failure,
    validating,
)
from generate_rights_cases import MemoryCollection
from legacy_stubs import MongoStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
ARMS_URL = "https://atbackend.sipri.org/api/p/trades/import-export-csv-str/"
MILEX_URL = "https://backend.sipri.org/api/p/excel-export/preview"
SYNTHETIC = {"armstransfers": "tests/fixtures/sipri/armstransfers_synthetic.json", "milex": "tests/fixtures/sipri/milex_synthetic.json"}
REAL = {"armstransfers": "sipri/armexp_response_2026-10-26.json", "milex": "sipri/milexp_response_2026-10-26.json", "milex_workbook": "sipri/SIPRI-Milex-data-1949-2025_v1.2.xlsx"}
SYNTHETIC["milex_workbook"] = "tests/fixtures/sipri/milex_workbook_synthetic.xlsx"
UNSDG_SAMPLES = {"UNSDG_RDPGDP": "tests/fixtures/unsdg/9_5_1_sample.json", "UNSDG_NRSRCH": "tests/fixtures/unsdg/9_5_2_sample.json"}
UNSDG_REAL = {"UNSDG_RDPGDP": "unsdg/9.5.1_2026-10-26.json", "UNSDG_NRSRCH": "unsdg/9.5.2_2026-10-26.json"}
UNSDG_SERIES = {"UNSDG_RDPGDP": "GB_XPD_RSDV", "UNSDG_NRSRCH": "GB_POP_SCIERD"}
ARMEXP_SCORE_FUNCTION_CASES = (("lower goalpost", 500.0), ("upper goalpost", 0.0), ("integer lower goalpost", 500), ("half way", 250.0), ("beyond the lower goalpost", 10704.0), ("fractional value", 499.5))
MILEXP_SCORE_FUNCTION_CASES = (("lower goalpost", 5.0), ("upper goalpost", 0.0), ("integer lower goalpost", 5), ("half way", 2.5), ("beyond the lower goalpost", 13.469841507576465), ("fractional value", 0.9905127014962755))
# The APPROVED SIPRI_MILEXP name table (MILEXP-1), the same as sspi.ingestion.sipri.APPROVED_MILEX_NAME_CORRECTIONS (the golden test checks).
MILEX_NAME_CORRECTIONS = {"Brunei": "BRN", "Congo, Republic": "COG", "Cote d'Ivoire": "CIV", "Gambia, The": "GMB", "Korea, North": "PRK", "German Democratic Republic": None}
# The APPROVED SIPRI_ARMEXP name table (ARMEXP-4), the same as sspi.ingestion.sipri.APPROVED_ARMS_NAME_CORRECTIONS.
ARMS_NAME_CORRECTIONS = {"Brunei": "BRN", "Bosnia-Herzegovina": "BIH"}
# MILEXP-2: shares of 1 or more verified row by row, the same as sspi.ingestion.sipri.MILEX_VERIFIED_LARGE_SHARES on the
# revised workbook; on the synthetic workbook an invented stand-in exercises the same rule (the golden file records it).
MILEX_VERIFIED_LARGE = {"real": [["Kuwait", 1991, 1.173498232086904]], "synthetic": [["Eritrea", 1991, 1.5]]}
# The workbook reading (MILEXP-4), the same as sspi.ingestion.sipri: window, markers, regions, excluded names.
MILEX_WINDOW = (1990, 2024)
MILEX_MARKERS = ["...", "xxx", ". ."]
MILEX_REGIONS = ["Africa", "North Africa", "sub-Saharan Africa", "Americas", "North America", "Central America and the Caribbean", "South America", "Asia & Oceania", "Central Asia", "East Asia", "South Asia", "South East Asia", "Oceania", "Europe", "Central Europe", "Eastern Europe", "Western Europe", "Middle East"]
MILEX_EXCLUDED = ["Czechoslovakia", "German Democratic Republic", "USSR", "Yemen, North", "Yugoslavia", "European Union"]
RDFUND_SCORE_FUNCTION_CASES = (("both at the upper goalposts", (4.0, 5000.0)), ("both zero", (0.0, 0.0)), ("beyond both", (6.34589, 9000.5)), ("fractional", (1.0121, 1218.32989)))


def frontmatter(path):
    import yaml

    with open(os.path.join(OLD_REPO, path)) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(f"methodology/pg/glb/{code.lower()}/methodology.md")
        return front["LowerGoalpost"], front["UpperGoalpost"]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", metavar="DIR", help="read the original answers from DIR and write the golden files there")
    args = parser.parse_args(argv)

    from sspi_flask_app.api.core.datasets import (
        dataset_cleaner_registry,
        dataset_collector_registry,
    )
    from sspi_flask_app.api.datasource.unsdg import extract_sdg, filter_sdg
    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.models.database import (
        sspi_clean_api_data,
        sspi_imputed_data,
        sspi_incomplete_indicator_data,
        sspi_indicator_data,
    )
    from sspi_flask_app.models.database.sspi_raw_api_data import SSPIRawAPIData

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = MetadataStub()
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            **({"fixtures": fixture} if isinstance(fixture, list) else {"fixture": fixture}),
        }

    def write(directory, name, payload):
        """Write a golden file, keeping the existing one where only ``generated_at`` would change."""
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        if os.path.exists(path):
            with open(path) as fh:
                existing = json.load(fh)
            if {**existing, "generated_from": {**existing["generated_from"], "generated_at": None}} == json.loads(json.dumps({**payload, "generated_from": {**payload["generated_from"], "generated_at": None}})):
                return
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)
            fh.write("\n")

    def read(relative):
        with open(os.path.join(args.real, relative) if args.real else os.path.join(NEW_REPO, relative), "rb") as fh:
            return fh.read()

    captured, outcomes = {}, {}
    original_score_indicator = utilities.score_indicator

    def capturing_score_indicator(documents, indicator_code, score_function, unit, *a, **k):
        captured.setdefault(indicator_code, score_function)
        outcomes[indicator_code] = original_score_indicator(documents, indicator_code, score_function, unit, *a, **k)
        return outcomes[indicator_code]

    def route_module(name):
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.pg.glb.{name}")
        module.app, module.parse_json = logger, (lambda value: value)
        if hasattr(module, "sspi_metadata"):
            module.sspi_metadata = metadata
        module.score_indicator = capturing_score_indicator
        return module

    sipri_fixtures = None if args.real else builder("sipri")
    suffix = "" if args.real else "_synthetic"

    def sipri(name, code, content):
        """The registered collector (requests.post answering with ``content``) and cleaner; (raw, cleaned, error, posted)."""
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.sipri.{code.lower()}")
        raw, posted = RawCapture(), []
        module.sspi_raw_api_data, module.sspi_metadata = raw, metadata
        module.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)

        def post(url, *a, **k):
            posted.append({"url": url, "headers": k.get("headers"), "json": k.get("json"), "verify": k.get("verify", True)})
            return types.SimpleNamespace(status_code=200, json=lambda: json.loads(content))

        module.requests = types.SimpleNamespace(post=post)
        messages = list(dataset_collector_registry[code](username="generator"))
        try:
            return raw, dataset_cleaner_registry[code](), None, posted, messages
        except Exception as exc:  # noqa: BLE001
            return raw, None, f"{type(exc).__name__}: {exc}", posted, messages

    def scored_routes(module, name, clean_documents):
        module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
        module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
        module.sspi_imputed_data = validating("sspi_imputed_data", sspi_imputed_data)
        if hasattr(module, "sspi_incomplete_indicator_data"):
            module.sspi_incomplete_indicator_data = validating("sspi_incomplete_indicator_data", sspi_incomplete_indicator_data)
        outcomes.pop(name.upper(), None)
        observed = unwrap(getattr(module, f"compute_{name}"))()
        incomplete = outcomes[name.upper()][1] if name.upper() in outcomes else []  # the compute route's, before impute overwrites it
        try:
            imputed, error = unwrap(getattr(module, f"impute_{name}"))(), None
        except Exception as exc:  # noqa: BLE001
            imputed, error = [], f"{type(exc).__name__}: {exc}"
        return observed, incomplete, imputed, error

    # ------------------------------------------------------------------- ARMEXP
    content = read(REAL["armstransfers"] if args.real else SYNTHETIC["armstransfers"])
    if not args.real:
        assert content == sipri_fixtures.build("armstransfers"), "committed answer differs from build_synthetic.py"
    raw, cleaned, error, posted, messages = sipri("armstransfers", "SIPRI_ARMEXP", content)
    assert error is None and posted and posted[0]["url"] == ARMS_URL, (error, posted)
    variants = {} if args.real else {name: sipri("armstransfers", "SIPRI_ARMEXP", sipri_fixtures.build("armstransfers", name))[1:3] for name in sipri_fixtures.VARIANTS["armstransfers"]}
    out = os.path.join(args.real, "sipri", "golden") if args.real else HERE
    fixture = REAL["armstransfers"] if args.real else SYNTHETIC["armstransfers"]
    write(
        out,
        f"sipri_armexp{suffix}_cases.json",
        {
            "generated_from": generated_from(["registered @dataset_collector for SIPRI_ARMEXP (requests.post answering with the fixture, raw insert captured)", "registered @dataset_cleaner for SIPRI_ARMEXP (legacy insert validation applied)"], fixture),
            "dataset_code": "SIPRI_ARMEXP",
            "request": posted[0],
            "observations": observation_records(cleaned),
            "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            "descriptions": sorted({d["Description"] for d in cleaned}),
            "invalid_variants": {name: {"cleaned": None if c is None else len(c), "legacy_error": e} for name, (c, e) in variants.items() if not name.startswith("probe_")},
        },
    )
    print(f"SIPRI_ARMEXP{suffix}: {len(cleaned)} observations; variants { {n: v for n, v in variants.items()} if len(str(variants)) < 400 else '...'}")
    module = route_module("armexp")
    observed, incomplete, imputed, impute_error = scored_routes(module, "armexp", cleaned)
    probe = None
    if not args.real:
        probe_clean = sipri("armstransfers", "SIPRI_ARMEXP", sipri_fixtures.build("armstransfers", "probe_are_exports"))[1]
        p_observed, _, p_imputed, p_error = scored_routes(module, "armexp", probe_clean)
        probe = {"observed_are_years": sorted(d["Year"] for d in p_observed if d["CountryCode"] == "ARE"), "legacy_impute_error": p_error, "imputed_scores": len(p_imputed)}
    front = frontmatter("methodology/pg/glb/armexp/methodology.md")
    _, _, empty_imputed, empty_error = scored_routes(module, "armexp", [])
    write(
        out,
        f"armexp{suffix}_cases.json",
        {
            "generated_from": generated_from([f"{module.__name__}.compute_armexp and impute_armexp (unwrapped view functions, collection handles stubbed, legacy insert validation applied)"], fixture),
            "indicator_code": "ARMEXP",
            "formula": f"goalpost(SIPRI_ARMEXP, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
            "unit": next(iter({d["Unit"] for d in observed})),
            "imputed_unit": next(iter({d["Unit"] for d in imputed})) if imputed else None,
            "impute_route_exists": True,
            "series_fill": {"order": ["forward", "backward", "interpolate"], "forward_to": 2023, "backward_to": 2000, "listed_recipients": ["ARE", "BGD", "IRQ"]},
            "observed_scores": records(observed, imputation=True),
            "incomplete_identities": identities(incomplete),
            "imputed_scores": records(imputed, imputation=True),
            "legacy_impute_error": impute_error,
            "legacy_output_conflicts": conflicts_of(observed, imputed),
            "probe_are_observed": probe,
            "empty_dataset": {"legacy_impute_error": empty_error, "imputed_scores": records(empty_imputed, imputation=True)},
            "score_function_cases": [{"case": n, "input": v, "score": captured["ARMEXP"](v)} for n, v in ARMEXP_SCORE_FUNCTION_CASES],
        },
    )
    print(f"ARMEXP{suffix}: {len(observed)} observed, {len(imputed)} imputed, impute error {impute_error}; probe {probe}")

    # ------------------------------------------------------------------- SIPRI_ARMEXP (approved correction, ARMEXP-4)
    arms_module = importlib.import_module("sspi_flask_app.api.core.datasets.sipri.sipri_armexp")
    legacy_matcher = arms_module.get_country_code
    arms_module.get_country_code = lambda name: ARMS_NAME_CORRECTIONS.get(name) or legacy_matcher(name)  # ONLY the approved table
    try:
        _, corrected_arms, corrected_error, _, _ = sipri("armstransfers", "SIPRI_ARMEXP", content)
    finally:
        arms_module.get_country_code = legacy_matcher
    assert corrected_error is None, corrected_error
    legacy_ids = {(d["CountryCode"], d["Year"]) for d in cleaned}
    added = [d for d in corrected_arms if (d["CountryCode"], d["Year"]) not in legacy_ids]
    assert len(corrected_arms) == len(cleaned) + len(added), "the correction must only add the rows the cleaner dropped"
    c_observed, c_incomplete, _, _ = scored_routes(module, "armexp", corrected_arms)
    write(
        out,
        f"sipri_armexp_corrected{suffix}_cases.json",
        {
            "generated_from": generated_from(["registered @dataset_collector and @dataset_cleaner for SIPRI_ARMEXP with ONLY the approved ARMEXP-4 name table patched into its get_country_code (legacy insert validation applied)", f"{module.__name__}.compute_armexp on those rows (unwrapped, stubbed, legacy validation)"], fixture),
            "dataset_code": "SIPRI_ARMEXP",
            "approved_name_corrections": ARMS_NAME_CORRECTIONS,
            "legacy_matcher_results": {name: legacy_matcher(name) for name in ARMS_NAME_CORRECTIONS},
            "legacy_clean_error": None,
            "legacy_dropped_rows": observation_records(added),
            "observations": observation_records(corrected_arms),
            "legacy_document_keys": sorted({k for d in corrected_arms for k in d}),
            "invalid_variants": {name: {"cleaned": None if c is None else len(c), "legacy_error": e} for name, (c, e) in variants.items() if not name.startswith("probe_")},
            "observed_scores": records(c_observed, imputation=True),
            "incomplete_identities": identities(c_incomplete),
        },
    )
    print(f"SIPRI_ARMEXP corrected{suffix}: {len(corrected_arms)} observations ({len(added)} added: {sorted({d['CountryCode'] for d in added})}), {len(c_observed)} observed scores")

    # ------------------------------------------------------------------- MILEXP (characterization)
    content = read(REAL["milex"] if args.real else SYNTHETIC["milex"])
    if not args.real:
        assert content == sipri_fixtures.build("milex"), "committed answer differs from build_synthetic.py"
    raw, cleaned, error, posted, messages = sipri("milex", "SIPRI_MILEXP", content)
    assert error is None and posted[0]["url"] == MILEX_URL, (error, posted)
    document = json.loads(content)
    (share,) = [s for s in document["Data"] if s.get("DataType") == "Share of GDP"]
    header = next(row for row in share["Rows"] if row and row[0] == "Country")
    by_name = {row[0]: row for row in share["Rows"] if row and len(row) == len(header)}
    alignment = []
    from sspi_flask_app.api.resources.utilities import get_country_code

    for name, row in by_name.items():
        if name == "Country":
            continue
        code = "PRK" if "north korea" in name.lower() else "KOR" if "south korea" in name.lower() else get_country_code(name)
        published = {int(float(header[i])): row[i] for i in range(2, len(header))}
        stored = {d["Year"]: d["Value"] for d in cleaned if d["CountryCode"] == code}
        alignment.append({"name": name, "country_code": code, "notes": row[1], "published": {str(y): v for y, v in sorted(published.items())}, "stored": {str(y): v for y, v in sorted(stored.items())}})
    module = route_module("milexp")
    observed, incomplete, imputed, impute_error = scored_routes(module, "milexp", cleaned)
    _, _, _, empty_error = scored_routes(module, "milexp", [])
    probe_clean = None if args.real else sipri("milex", "SIPRI_MILEXP", sipri_fixtures.build("milex", "probe_empty_share"))[1]
    front = frontmatter("methodology/pg/glb/milexp/methodology.md")
    write(
        os.path.join(args.real, "sipri", "golden") if args.real else HERE,
        "milexp_characterization_cases.json" if not args.real else "milexp_cases.json",
        {
            "generated_from": generated_from(["registered @dataset_collector and @dataset_cleaner for SIPRI_MILEXP", f"{module.__name__}.compute_milexp and impute_milexp (unwrapped, stubbed, legacy validation)"], REAL["milex"] if args.real else SYNTHETIC["milex"]),
            "dataset_code": "SIPRI_MILEXP",
            "request": posted[0],
            "share_of_gdp_header": header,
            "cleaned_observations": observation_records(cleaned),
            "alignment": alignment,
            "formula": f"goalpost(SIPRI_MILEXP, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
            "observed_unit": next(iter({d["Unit"] for d in observed})) if observed else None,
            "imputed_unit": next(iter({d["Unit"] for d in imputed})) if imputed else None,
            "observed_scores": records(observed, imputation=True),
            "imputed_scores": records(imputed, imputation=True),
            "legacy_impute_error": impute_error,
            "legacy_output_conflicts": conflicts_of(observed, imputed),
            "iceland": {"observed_rows": [d for d in cleaned if d["CountryCode"] == "ISL"], "imputed_years": sorted(d["Year"] for d in imputed if d["CountryCode"] == "ISL"), "imputed_values": sorted({x["Value"] for d in imputed if d["CountryCode"] == "ISL" for x in d["Datasets"]})},
            "empty_dataset": {"legacy_impute_error": empty_error},
            "probe_empty_share": None if probe_clean is None else {"cleaned": probe_clean},
        },
    )
    print(f"MILEXP{suffix}: {len(cleaned)} cleaned, {len(observed)} observed, {len(imputed)} imputed, impute error {impute_error}, empty {empty_error}")

    # ------------------------------------------------------------------- MILEXP (approved source: the revised workbook)
    legacy_years = {}
    for row in alignment:  # MILEXP-1: what the legacy cleaner stored for each name and year
        if row["name"] in MILEX_NAME_CORRECTIONS:
            continue
        published = {int(y): v for y, v in row["published"].items()}
        offsets = {k for k in (10, 11) if row["stored"] and all((int(y) - k) in published and published[int(y) - k] not in ("...", "xxx", ". .") and (float(published[int(y) - k]) * 100 if float(published[int(y) - k]) < 1 else float(published[int(y) - k])) == v for y, v in row["stored"].items())}
        legacy_years[row["name"]] = sorted(offsets)
    legacy_divergence = {
        "source": "the pinned legacy collector and cleaner on the API answer (milexp_characterization_cases.json; opt-in milexp_cases.json)",
        "stored_years_late_by": {str(k): sorted(n for n, o in legacy_years.items() if o == [k]) for k in (10, 11)},
        "names": {name: {"legacy_code": next((r["country_code"] for r in alignment if r["name"] == name), None), "approved": code} for name, code in MILEX_NAME_CORRECTIONS.items()},
        "kept_unscaled": sorted([r["name"], int(y), v] for r in alignment for y, v in r["published"].items() if v not in ("...", "xxx", ". .", "", None) and float(v) >= 1),
    }

    def workbook_rows(content, verified):
        """The workbook's "Share of GDP" sheet read independently of the new backend: years from the header, 1990-2024;
        markers missing; every number a fraction multiplied by 100 (a share of 1 or more only where verified); names by
        the approved table, then the legacy Korea rules and matcher; regions and excluded names skipped. Checked by the
        legacy clean collection's validation. Returns (rows, skipped names, missing cells)."""
        import io as _io

        import openpyxl

        book = openpyxl.load_workbook(_io.BytesIO(content), read_only=True, data_only=True)
        sheet = [tuple(r) for r in book["Share of GDP"].iter_rows(values_only=True)]
        book.close()
        at = next(i for i, r in enumerate(sheet) if r and r[0] == "Country")
        columns = {y: i for i, y in enumerate(sheet[at]) if isinstance(y, int) and MILEX_WINDOW[0] <= y <= MILEX_WINDOW[1]}
        large = {(n, y): v for n, y, v in verified}
        out, skipped, missing = [], [], 0
        for r in sheet[at + 1 :]:
            if all(c is None for c in r) or r[0] in MILEX_REGIONS:
                continue
            name = r[0]
            if name in MILEX_NAME_CORRECTIONS:
                code = MILEX_NAME_CORRECTIONS[name]
            elif "north korea" in name.lower():
                code = "PRK"
            elif "south korea" in name.lower():
                code = "KOR"
            else:
                code = get_country_code(name)
            if not code or len(code) != 3:
                assert name in MILEX_EXCLUDED, name
                skipped.append(name)
                continue
            for year, column in columns.items():
                cell = r[column]
                if cell in MILEX_MARKERS:
                    missing += 1
                    continue
                assert isinstance(cell, (int, float)) and not isinstance(cell, bool), (name, year, cell)
                if cell >= 1:
                    assert large.get((name, year)) == cell, (name, year, cell)
                out.append({"CountryCode": code, "Year": year, "Value": float(cell) * 100, "Unit": "Percent of GDP", "DatasetCode": "SIPRI_MILEXP", "Description": "Military expenditure (local currency at current prices) according to the calendar year as a percentage of GDP."})
        sspi_clean_api_data.validate_documents_format(out)
        return out, skipped, missing

    def workbook_case(content, verified):
        rows, skipped, missing = workbook_rows(content, verified)
        observed, incomplete, imputed, error = scored_routes(module, "milexp", rows)
        return rows, skipped, missing, {
            "observed_scores": records(observed, imputation=True),
            "incomplete_identities": identities(incomplete),
            "imputed_scores": records(imputed, imputation=True),
            "unit": next(iter({d["Unit"] for d in observed})) if observed else None,
            "imputed_unit": next(iter({d["Unit"] for d in imputed})) if imputed else None,
            "legacy_impute_error": error,
            "legacy_output_conflicts": conflicts_of(observed, imputed),
            "iceland": {"observed_years": sorted(d["Year"] for d in rows if d["CountryCode"] == "ISL"), "imputed_years": sorted(d["Year"] for d in imputed if d["CountryCode"] == "ISL")},
        }

    verified = MILEX_VERIFIED_LARGE["real" if args.real else "synthetic"]
    workbook_content = read(REAL["milex_workbook"] if args.real else SYNTHETIC["milex_workbook"])
    rows, skipped, missing, scores = workbook_case(workbook_content, verified)
    variants_out, probe_partial = [], None
    if not args.real:
        v_rows, _, _, v_scores = workbook_case(sipri_fixtures.build("milex_workbook", "iceland_published_zero"), verified)
        variants_out.append({"name": "iceland_published_zero", "note": "Iceland published as 0 in every year, as in the revised workbook (MILEXP-5)", "iceland_observations": observation_records([d for d in v_rows if d["CountryCode"] == "ISL"]), **v_scores})
        p_rows, _, _, p_scores = workbook_case(sipri_fixtures.build("milex_workbook", "iceland_partial"), verified)
        probe_partial = {"iceland_observations": observation_records([d for d in p_rows if d["CountryCode"] == "ISL"]), "legacy_impute_error": p_scores["legacy_impute_error"], "imputed_scores": len(p_scores["imputed_scores"])}
    comparison = None
    if args.real:  # the API answer (2025 edition) against the workbook (2026 edition), cell by cell, 1990-2024
        import io as _io

        import openpyxl

        book = openpyxl.load_workbook(_io.BytesIO(workbook_content), read_only=True, data_only=True)
        sheet = [tuple(r) for r in book["Share of GDP"].iter_rows(values_only=True)]
        book.close()
        at = next(i for i, r in enumerate(sheet) if r and r[0] == "Country")
        wb_cells = {r[0]: dict(zip(sheet[at][2:], r[2:])) for r in sheet[at + 1 :] if r and r[0]}
        api_rows = {r[0]: dict(zip((int(float(h)) for h in header[2:]), r[2:])) for r in share["Rows"] if r and len(r) == len(header) and r[0] != "Country"}
        number = lambda v: None if v in ("...", "xxx", ". .", "", None) else float(v)
        differences = []
        for name in api_rows:
            for year in range(MILEX_WINDOW[0], MILEX_WINDOW[1] + 1):
                a, w = api_rows[name][year], wb_cells[name].get(year)
                na, nw = number(a), number(w)
                if na is None and nw is None:
                    continue
                kind = "workbook only" if na is None else "api only" if nw is None else None if na == nw else "differ"
                if kind:
                    differences.append({"name": name, "year": year, "api": a, "workbook": w, "kind": kind})
        comparison = {"api_title": share["Rows"][0][0], "workbook_title": sheet[0][0], "identical": sum(1 for n in api_rows for y in range(MILEX_WINDOW[0], MILEX_WINDOW[1] + 1) if number(api_rows[n][y]) is not None and number(api_rows[n][y]) == number(wb_cells[n].get(y))), "differences": differences}
    write(
        os.path.join(args.real, "sipri", "golden") if args.real else HERE,
        f"milexp_workbook{suffix}_cases.json",
        {
            "generated_from": generated_from([
                "SIPRI_MILEXP's approved source, the revised SIPRI workbook, read by this generator independently of the new backend (NOT legacy code: the legacy collector read the API); the approved MILEXP-1 and MILEXP-2 corrections; checked by the legacy clean collection's validation",
                f"{module.__name__}.compute_milexp and impute_milexp on those rows (unwrapped, stubbed, legacy validation): legacy scoring on identical inputs",
            ], REAL["milex_workbook"] if args.real else SYNTHETIC["milex_workbook"]),
            "dataset_code": "SIPRI_MILEXP",
            "indicator_code": "MILEXP",
            "not_legacy_observations": "the observations are an independent reading of the workbook, not output of the legacy cleaner, which never read it",
            "approved_name_corrections": MILEX_NAME_CORRECTIONS,
            "approved_other_repairs": ["years from the header labels", "every fraction multiplied by 100; a share of 1 or more only where verified", "the revised workbook as the single source, 1990-2024"],
            "verified_large": verified,
            "window": list(MILEX_WINDOW),
            "legacy_divergence": legacy_divergence,
            "skipped_names": skipped,
            "missing_cells": missing,
            "observations": observation_records(rows),
            "formula": "goalpost(SIPRI_MILEXP, 5, 0)",
            **scores,
            "impute_route_exists": True,
            "variants": variants_out,
            "probe_iceland_partial": probe_partial,
            "api_comparison": comparison,
            "score_function_cases": [{"case": n, "input": v, "score": captured["MILEXP"](v)} for n, v in MILEXP_SCORE_FUNCTION_CASES],
        },
    )
    print(f"MILEXP workbook{suffix}: {len(rows)} rows, skipped {skipped}, missing {missing}; {len(scores['observed_scores'])} observed, {len(scores['imputed_scores'])} imputed, error {scores['legacy_impute_error']}, conflicts {[len(v) for v in scores['legacy_output_conflicts'].values()]}; variants {[(v['name'], v['legacy_impute_error'], [len(x) for x in v['legacy_output_conflicts'].values()]) for v in variants_out]}; partial {probe_partial and probe_partial['legacy_impute_error']}")

    # ------------------------------------------------------------------- RDFUND
    clean = {}
    sample_paths = []
    for code, path in (UNSDG_REAL if args.real else UNSDG_SAMPLES).items():
        rows = json.loads(read(path))
        rows = rows if args.real else rows["data"]
        sample_paths.append(path)
        clean[code] = filter_sdg(extract_sdg([{"Raw": copy.deepcopy(r)} for r in rows]), {UNSDG_SERIES[code]: code}, {"units": "Unit", "seriesDescription": "Description"}, ["goal", "indicator", "series", "seriesCount", "target", "geoAreaCode", "geoAreaName"])
        sspi_clean_api_data.validate_documents_format(clean[code])
    module = route_module("rdfund")
    documents = clean["UNSDG_RDPGDP"] + clean["UNSDG_NRSRCH"]
    observed, incomplete, imputed, impute_error = scored_routes(module, "rdfund", documents)
    reference = []
    for code in UNSDG_SERIES:
        values = [d["Value"] for d in clean[code]]
        reference.append({"dataset_code": code, "count": len(values), "mean": sum(values) / len(values)})
    probe = None
    if not args.real:
        bgd = {"DatasetCode": "UNSDG_NRSRCH", "CountryCode": "BGD", "Year": 2015, "Value": 150.0, "Unit": "PER_1000000_POP", "Description": "invented probe row"}
        _, _, p_imputed, p_error = scored_routes(module, "rdfund", documents + [bgd])
        probe = {"row": bgd, "legacy_impute_error": p_error, "imputed_scores": len(p_imputed)}
    _, _, _, empty_error = scored_routes(module, "rdfund", [])
    write(
        os.path.join(args.real, "unsdg", "golden") if args.real else HERE,
        "rdfund_cases.json",
        {
            "generated_from": generated_from(["extract_sdg + filter_sdg as in unsdg_rdpgdp.py and unsdg_nrsrch.py", f"{module.__name__}.compute_rdfund and impute_rdfund (unwrapped, stubbed, legacy validation)"], sample_paths),
            "indicator_code": "RDFUND",
            "formula": "(goalpost(UNSDG_RDPGDP, 0, 4) + goalpost(UNSDG_NRSRCH, 0, 5000)) / 2",
            "methodology_score_function": frontmatter("methodology/pg/glb/rdfund/methodology.md")["ScoreFunction"].strip(),
            "unit": next(iter({d["Unit"] for d in observed})),
            "imputed_unit": next(iter({d["Unit"] for d in imputed})) if imputed else None,
            "impute_route_exists": True,
            "series_fill": {"order": ["forward", "backward", "interpolate"], "forward_to": 2023, "backward_to": 2000, "listed_recipients": {"UNSDG_NRSRCH": ["PER", "BGD", "ISR"], "UNSDG_RDPGDP": ["BGD"]}, "observed_rows_scored_with_fills": True},
            "observed_scores": records(observed, imputation=True),
            "incomplete_identities": identities(incomplete),
            "imputed_scores": records(imputed, imputation=True),
            "legacy_impute_error": impute_error,
            "legacy_output_conflicts": conflicts_of(observed, imputed),
            "reference_class": reference,
            "probe_bgd_observed": probe,
            "empty_dataset": {"legacy_impute_error": empty_error},
            "score_function_cases": [{"case": n, "input": list(v), "score": captured["RDFUND"](*v)} for n, v in RDFUND_SCORE_FUNCTION_CASES],
        },
    )
    print(f"RDFUND{suffix}: {len(observed)} observed, {len(incomplete)} incomplete, {len(imputed)} imputed, error {impute_error}; probe {probe and probe['legacy_impute_error']}")

    # ------------------------------------------------------------------- FORAID (characterization)
    if not args.real:
        module = importlib.import_module("sspi_flask_app.api.core.sspi.pg.glb.foraid")
        module.app = logger
        module.sspi_raw_api_data = SSPIRawAPIData(MemoryCollection())
        module.sspi_clean_api_data = MongoStub("sspi_clean_api_data")
        module.sspi_incomplete_indicator_data = MongoStub("sspi_incomplete_indicator_data", log=module.sspi_clean_api_data.log)
        error = failure(unwrap(module.compute_foraid))
        write(
            HERE,
            "foraid_characterization_cases.json",
            {
                "generated_from": generated_from([f"{module.__name__}.compute_foraid (unwrapped, sspi_raw_api_data = SSPIRawAPIData over an in-memory collection)"], "none: the route fails before reading data"),
                "indicator_code": "FORAID",
                "compute_route_error": error,
                "compute_route_log": module.sspi_clean_api_data.log,
                "impute_route_exists": hasattr(module, "impute_foraid"),
                "collectors": {code: code in dataset_collector_registry for code in ("OECD_TOTDON", "OECD_TONREC", "WB_POPULN", "WB_GDPMKT")},
                "cleaners": {code: code in dataset_cleaner_registry for code in ("OECD_TOTDON", "OECD_TONREC", "WB_POPULN", "WB_GDPMKT")},
                "methodology_score_function": frontmatter("methodology/pg/glb/foraid/methodology.md")["ScoreFunction"].strip(),
                "route_score_arguments": ["TOTDON", "TOTREC", "POPULN", "GDPMKT"],
                "route_writes_scores_to": "sspi_clean_api_data",
            },
        )
        print(f"FORAID: {error}")


if __name__ == "__main__":
    main()
