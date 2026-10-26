"""Generate the Public Safety golden files with the pinned legacy code:

    wb_murder_cases.json, murder_cases.json
        from the committed World Bank sample tests/fixtures/wb/VC.IHR.PSRC.P5_sample.json
    unodc_pripop_synthetic_cases.json, prison_synthetic_cases.json
        from the committed synthetic workbook tests/fixtures/unodc/data_cts_prisons_and_prisoners_synthetic.xlsx
    itu_cybsec_synthetic_cases.json, cybsec_synthetic_cases.json
        from the committed synthetic transcription tests/fixtures/itu/gci-local-indicator-summary_synthetic.csv
    secapp_characterization_cases.json
        what the pinned FSI collector, cleaner and compute route do on their own
    fsi_secapp_synthetic_cases.json, secapp_synthetic_cases.json
        from the committed synthetic workbooks tests/fixtures/fsi/fsi-{2018,2021,2023}_synthetic.xlsx

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \\
        /path/to/sspi-backend/tests/golden/generate_public_safety_cases.py [--real DIR] [section ...]

Sections: murder, prison, cybsec, secapp (default: all four).

``--real DIR`` reads the original sources kept outside the repository
(docs/data-governance-review.md, GOV-3 and GOV-4) instead of the committed
synthetic ones, and writes to DIR, never to the repository:

* prison: ``DIR/unodc/data_cts_prisons_and_prisoners_2026-09-30.xlsx`` ->
  ``DIR/unodc/golden/unodc_pripop_cases.json``, ``prison_cases.json``;
* cybsec: ``DIR/itu/gci-local-indicator-summary.csv`` ->
  ``DIR/itu/golden/itu_cybsec_cases.json``, ``cybsec_cases.json`` (the
  legacy cleaner's output, the clean collection's refusal of it, the rows
  with only the approved correction and the legacy scores on them);
* secapp: the 18 workbooks in ``DIR/fsi/`` ->
  ``DIR/fsi/golden/fsi_secapp_cases.json``, ``secapp_cases.json``.

Everything recorded is the legacy code's own output:

* MURDER: the registered ``@dataset_cleaner`` for WB_MURDER reads the World
  Bank rows (one raw document per API row); ``compute_murder`` and
  ``impute_murder`` run unwrapped with their collection handles replaced by
  ``MongoStub`` collections whose inserts first apply the legacy
  collections' own validation;
* PRISON: the registered ``@dataset_collector`` runs with ``requests.get``
  answering with the workbook's bytes and its raw insert captured (the CSV
  text it made of the first sheet); the registered cleaner reads that
  document and its insert is checked by the legacy clean collection's
  ``validate_documents_format``; ``compute_prison`` and ``impute_prison``
  run as MURDER's do, with ``impute_reference_class_average`` observed;
* CYBSEC: the pinned collector and cleaner read
  ``local/gci-local-indicator-summary.csv`` relative to the working
  directory. At the pinned commit that file is not there (it was moved to
  ``local/CYBSEC/`` on 2025-03-27); both are run in the legacy repository to
  record the failure, then in a scratch working directory that holds the
  fixture at the old path. The clean insert is validated as above;
  ``compute_cybsec`` runs as above;
* SECAPP: the collector's link discovery is run on what it parses (the
  address string, not the page), the cleaner on the document shape the
  collector stores, and the cleaner and ``compute_secapp`` on a few
  synthetic records in the shape the cleaner reads (no FSI data). Then,
  on the FSI workbooks: (A) the registered cleaner on the raw documents the
  working collector of March 2025 stored (``read_excel`` rows under
  ``Raw.json``, round-tripped through BSON and ``json_util``), and how it
  fails; (B) the same cleaner with only the approved repair (names
  stripped, five spellings mapped, the dataset code set), checked by the
  legacy clean collection's validation; (C) ``compute_secapp`` on (B);
* CYBSEC, likewise: (A) the legacy failure on the five uncoded spellings,
  (B) the cleaner's rows with only the approved correction, (C) the legacy
  scores on them.

The score functions are lambdas inside the routes. ``score_indicator`` is
wrapped to observe them, and each is evaluated on inputs no fixture holds
(both goalposts, beyond them, half way).

Invalid variants of the synthetic sources (see their ``build_synthetic.py``)
are also run through the legacy collector and cleaner, recording how legacy
failed.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import re
import subprocess
import tempfile
import types
from datetime import datetime, timezone

from generate_education_cases import source_rows
from generate_inequality_cases import identities, observation_records, records, unwrap
from generate_legacy_cleaner_cases import RawStub
from legacy_stubs import MongoStub, legacy_skipped

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
SECTIONS = ("murder", "prison", "cybsec", "secapp")
WB_SAMPLE = "tests/fixtures/wb/VC.IHR.PSRC.P5_sample.json"
UNODC_SYNTHETIC = "tests/fixtures/unodc/data_cts_prisons_and_prisoners_synthetic.xlsx"
ITU_SYNTHETIC = "tests/fixtures/itu/gci-local-indicator-summary_synthetic.csv"
UNODC_REAL = "unodc/data_cts_prisons_and_prisoners_2026-09-30.xlsx"
ITU_REAL = "itu/gci-local-indicator-summary.csv"
UNODC_URL = "https://dataunodc.un.org/sites/dataunodc.un.org/files/data_cts_prisons_and_prisoners.xlsx"  # the legacy collector's literal
ITU_LEGACY_PATH = "local/gci-local-indicator-summary.csv"  # the legacy collector's and cleaner's literal
ITU_COMMITTED_PATH = "local/CYBSEC/gci-local-indicator-summary.csv"
# The project owner's approved source-representation correction (CYBSEC-1, 2026-10-25); the same table as
# sspi.ingestion.itu.APPROVED_NAME_CORRECTIONS (test_golden_cybsec.py checks they are equal).
ITU_APPROVED_NAME_CORRECTIONS = {"Cote d'Ivoire": "CIV", "Macedonia": "MKD", "Micronesia": "FSM", "State of Palestine": "PSE", "Vatican": "VAT"}
# The FSI repair (SECAPP-1), the same table as sspi.ingestion.fsi.APPROVED_NAME_CORRECTIONS (test_golden_secapp.py checks).
FSI_APPROVED_NAME_CORRECTIONS = {"Cote d'Ivoire": "CIV", "Macedonia": "MKD", "Micronesia": "FSM", "Palestine": "PSE", "North Korea": "PRK"}
MURDER_SCORE_FUNCTION_CASES = (("lower goalpost", 20.0), ("upper goalpost", 0.0), ("integer lower goalpost", 20), ("half way", 10.0), ("beyond the lower goalpost", 85.8773343009539), ("fractional value", 0.734492430713877))
PRISON_SCORE_FUNCTION_CASES = (("lower goalpost", 540.0), ("upper goalpost", 40.0), ("integer lower goalpost", 540), ("half way", 290.0), ("beyond the lower goalpost", 700.0), ("below the upper goalpost", 0.0), ("fractional value", 171.1234567890124))
CYBSEC_SCORE_FUNCTION_CASES = (("lower goalpost", 0.0), ("upper goalpost", 1.0), ("integer upper goalpost", 1), ("half way", 0.5), ("fractional value", 0.9747))
SECAPP_SCORE_FUNCTION_CASES = (("lower goalpost", 10.0), ("upper goalpost", 0.0), ("half way", 5.0), ("fractional value", 3.5))


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "pg", "saf", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def validating(name, legacy_collection, documents=()):
    """A MongoStub whose inserts are first checked the way the legacy collection checked them."""

    class Validating(MongoStub):
        def insert_many(self, docs):
            legacy_collection.validate_documents_format(docs)
            return super().insert_many(docs)

    return Validating(name, documents)


class RawCapture:
    """Stands in for ``sspi_raw_api_data``: keeps what the collector inserts and serves it to the cleaner."""

    def __init__(self):
        self.inserted = []

    def raw_insert_one(self, document, source_info, **kwargs):
        self.inserted.append({"Raw": document, "Source": source_info})
        return 1

    def fetch_raw_data(self, source_info, **kwargs):
        return [json.loads(json.dumps(d)) for d in self.inserted]


def failure(call):
    try:
        call()
    except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
        return f"{type(exc).__name__}: {exc}"
    return None


def conflicts_of(observed, imputed):
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    return {
        "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
        "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
    }


def builder(organization):
    """``tests/fixtures/<organization>/build_synthetic.py``, loaded under its own module name."""
    import importlib.util

    path = os.path.join(NEW_REPO, "tests", "fixtures", organization, "build_synthetic.py")
    spec = importlib.util.spec_from_file_location(f"{organization}_build_synthetic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def working_directory(path):
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", metavar="DIR", help="read the original sources from DIR and write the golden files there")
    parser.add_argument("sections", nargs="*", choices=SECTIONS)
    args = parser.parse_args(argv)
    sections = args.sections or (("prison", "cybsec", "secapp") if args.real else SECTIONS)
    if args.real:
        assert set(sections) <= {"prison", "cybsec", "secapp"}, "--real covers the prison, cybsec and secapp sections only"

    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.models.database import sspi_clean_api_data, sspi_imputed_data, sspi_incomplete_indicator_data, sspi_indicator_data

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
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    captured, outcomes = {}, {}
    original_score_indicator = utilities.score_indicator

    def capturing_score_indicator(documents, indicator_code, score_function, unit, *a, **k):
        captured.setdefault(indicator_code, score_function)  # the compute route's lambda: its first call
        outcomes[indicator_code] = original_score_indicator(documents, indicator_code, score_function, unit, *a, **k)
        return outcomes[indicator_code]

    def route_module(name):
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.pg.saf.{name}")
        module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata
        module.score_indicator = capturing_score_indicator
        return module

    def score_cases(code, cases):
        function = captured[code]
        return [{"case": name, "input": value, "score": function(value)} for name, value in cases]

    # ------------------------------------------------------------------- MURDER
    if "murder" in sections:
        from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

        rows = source_rows("WB", WB_SAMPLE)
        dataset = importlib.import_module("sspi_flask_app.api.core.datasets.wb.wb_murder")
        dataset.sspi_raw_api_data = RawStub(rows)
        dataset.sspi_clean_api_data, dataset.sspi_metadata = validating("sspi_clean_api_data", sspi_clean_api_data), metadata
        cleaned = dataset_cleaner_registry["WB_MURDER"]()
        assert cleaned and all(d["DatasetCode"] == "WB_MURDER" for d in cleaned)
        skipped, without_code, missing = legacy_skipped(rows)
        from pycountry import countries

        zeros = sorted([row["countryiso3code"] or row["country"]["id"], int(row["date"])] for row in rows if row["value"] == 0 and countries.get(alpha_3=row["countryiso3code"] or row["country"]["id"]) is not None)
        write(
            HERE,
            "wb_murder_cases.json",
            {
                "generated_from": generated_from([f"{dataset.__name__}.clean_wb_murder (registered @dataset_cleaner, Mongo handles stubbed, legacy insert validation applied)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], WB_SAMPLE),
                "dataset_code": "WB_MURDER",
                "source_indicator": "VC.IHR.PSRC.P5",
                "observations": observation_records(cleaned),
                "descriptions": sorted({d["Description"] for d in cleaned}),
                "skipped_areas": skipped,
                "rows_without_area_code": without_code,
                "empty_source_values": missing,
                "zero_values_dropped": zeros,
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        print(f"WB_MURDER: {len(cleaned)} observations, {len(skipped)} skipped areas, {missing} empty or zero values (zeros: {zeros})")

        module = route_module("murder")

        def murder(clean_documents):
            module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
            module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
            module.sspi_imputed_data = validating("sspi_imputed_data", sspi_imputed_data)
            observed = unwrap(module.compute_murder)()
            try:
                imputed, error = unwrap(module.impute_murder)(), None
            except Exception as exc:  # noqa: BLE001
                imputed, error = [], f"{type(exc).__name__}: {exc}"
            assert len(module.sspi_indicator_data.documents) == len(observed) and len(module.sspi_imputed_data.documents) == len(imputed)
            return observed, imputed, error, conflicts_of(observed, imputed)

        observed, imputed, error, conflicts = murder(cleaned)
        _, incomplete = outcomes["MURDER"]
        empty_observed, empty_imputed, empty_error, _ = murder([])
        front = frontmatter("MURDER")
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (observed_unit,), (imputed_unit,) = {d["Unit"] for d in observed}, {d["Unit"] for d in imputed}
        write(
            HERE,
            "murder_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "registered @dataset_cleaner function for WB_MURDER (Mongo handles stubbed)",
                        f"{module.__name__}.compute_murder (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                        f"{module.__name__}.impute_murder (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                    ],
                    WB_SAMPLE,
                ),
                "indicator_code": "MURDER",
                "formula": f"goalpost(WB_MURDER, {lg}, {ug})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"].strip(),
                "goalposts": [lg, ug],
                "unit": observed_unit,
                "imputed_unit": imputed_unit,
                "impute_route_exists": True,
                "series_fill": {"order": ["interpolate", "forward", "backward"], "forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year", "series_id": ["CountryCode", "DatasetCode"]},
                "observed_scores": records(observed, imputation=True),
                "incomplete_identities": identities(incomplete),
                "imputed_scores": records(imputed, imputation=True),
                "legacy_impute_error": error,
                "legacy_output_conflicts": conflicts,
                "empty_dataset": {"observed_scores": records(empty_observed, imputation=True), "imputed_scores": records(empty_imputed, imputation=True), "legacy_impute_error": empty_error},
                "score_function_cases": score_cases("MURDER", MURDER_SCORE_FUNCTION_CASES),
            },
        )
        methods = {}
        for d in imputed:
            method = d.get("ImputationMethod") or d["Datasets"][0].get("ImputationMethod")
            methods[method] = methods.get(method, 0) + 1
        print(f"MURDER: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}), {len(imputed)} imputed {methods}, conflicts {conflicts}; empty: impute error {empty_error}")

    # ------------------------------------------------------------------- PRISON
    if "prison" in sections:
        from sspi_flask_app.api.core.datasets import dataset_cleaner_registry, dataset_collector_registry

        dataset = importlib.import_module("sspi_flask_app.api.core.datasets.unodc.unodc_pripop")
        dataset.sspi_metadata = metadata
        requested = []

        def run_dataset(content):
            raw = RawCapture()
            dataset.sspi_raw_api_data = raw
            dataset.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)

            def get(url, *a, **k):
                requested.append(url)
                return types.SimpleNamespace(status_code=200, content=content)

            dataset.requests = types.SimpleNamespace(get=get)
            messages = list(dataset_collector_registry["UNODC_PRIPOP"](username="generator"))
            assert len(raw.inserted) == 1, messages
            try:
                return raw, dataset_cleaner_registry["UNODC_PRIPOP"](), None
            except Exception as exc:  # noqa: BLE001
                return raw, None, f"{type(exc).__name__}: {exc}"

        if args.real:
            with open(os.path.join(args.real, UNODC_REAL), "rb") as fh:
                content = fh.read()
            fixture, out, suffix = UNODC_REAL, os.path.join(args.real, "unodc", "golden"), ""
            variants = {}
        else:
            unodc_synthetic = builder("unodc")
            with open(os.path.join(NEW_REPO, UNODC_SYNTHETIC), "rb") as fh:
                content = fh.read()
            assert unodc_synthetic.cells(content) == unodc_synthetic.cells(unodc_synthetic.build()), "committed workbook differs from build_synthetic.py"
            fixture, out, suffix = UNODC_SYNTHETIC, HERE, "_synthetic"
            variants = {name: run_dataset(unodc_synthetic.build(name))[2] for name in unodc_synthetic.VARIANTS}
        raw, cleaned, error = run_dataset(content)
        assert error is None, error
        assert set(requested) == {UNODC_URL}, requested
        (raw_document,) = raw.inserted
        import pandas as pd

        table = pd.read_csv(io.StringIO(raw_document["Raw"]), skiprows=2)
        kept = table[(table["Age"] == "Total") & (table["Category"] == "Total") & (table["Dimension"] == "Total") & (table["Indicator"] == "Persons held") & (table["Sex"] == "Total") & (table["Unit of measurement"] == "Rate per 100,000 population")]
        complete = kept.dropna(subset=["Iso3_code", "Year", "VALUE"])
        dropped_codes = sorted({(c, n) for c, n in zip(complete["Iso3_code"], complete["Country"], strict=True) if len(c) != 3})
        regions = complete[complete["Iso3_code"].isin(["GBR_NI", "GBR_E_W", "GBR_S"])]
        reporting = {int(year): sorted(group["Iso3_code"]) for year, group in regions.groupby("Year")}
        write(
            out,
            f"unodc_pripop{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"{dataset.__name__}.collect_unodc_pripop (registered @dataset_collector, requests.get answering with the workbook, raw insert captured)",
                        f"{dataset.__name__}.clean_unodc_pripop (registered @dataset_cleaner, legacy insert validation applied)",
                    ],
                    fixture,
                ),
                "dataset_code": "UNODC_PRIPOP",
                "requested_url": UNODC_URL,
                "raw_source_info": raw_document["Source"],
                "observations": observation_records(cleaned),
                "skipped_areas": [list(c) for c in dropped_codes],
                "empty_source_values": int(kept["VALUE"].isna().sum()),
                "regional_mean_years": {str(year): codes for year, codes in sorted(reporting.items())},
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
                "invalid_variants": variants,
            },
        )
        print(f"UNODC_PRIPOP{suffix}: {len(cleaned)} observations, skipped {dropped_codes}, {int(kept['VALUE'].isna().sum())} empty values; variants {variants}")

        module = route_module("prison")
        reference_calls = []
        original_reference = module.impute_reference_class_average

        def reference_class(country_code, start_year, end_year, item_type, item_code, ref_data):
            values = [x["Value"] for x in ref_data]
            reference_calls.append({"country_code": country_code, "years": [start_year, end_year], "item_type": item_type, "item_code": item_code, "reference_count": len(values), "mean": sum(values) / len(values) if values else None})
            return original_reference(country_code, start_year, end_year, item_type, item_code, ref_data)

        module.impute_reference_class_average = reference_class

        def prison(clean_documents):
            reference_calls.clear()
            module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
            module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
            module.sspi_incomplete_indicator_data = validating("sspi_incomplete_indicator_data", sspi_incomplete_indicator_data)
            module.sspi_imputed_data = validating("sspi_imputed_data", sspi_imputed_data)
            observed = unwrap(module.compute_prison)()
            try:
                imputed, error = unwrap(module.impute_prison)(), None
            except Exception as exc:  # noqa: BLE001
                imputed, error = [], f"{type(exc).__name__}: {exc}"
            assert len(module.sspi_indicator_data.documents) == len(observed) and len(module.sspi_imputed_data.documents) == len(imputed)
            return observed, imputed, error, conflicts_of(observed, imputed), list(reference_calls)

        observed, imputed, error, conflicts, calls = prison(cleaned)
        _, incomplete = outcomes["PRISON"]
        empty_observed, empty_imputed, empty_error, _, _ = prison([])
        unit = cleaned[0]["Unit"]
        chinese = [{"DatasetCode": "UNODC_PRIPOP", "CountryCode": "CHN", "Year": year, "Value": value, "Unit": unit} for year, value in ((2005, 120.0), (2010, 125.0))]
        _, probe_imputed, probe_error, probe_conflicts, _ = prison(cleaned + chinese)
        front = frontmatter("PRISON")
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (observed_unit,), (imputed_unit,) = {d["Unit"] for d in observed}, {d["Unit"] for d in imputed}
        write(
            out,
            f"prison{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "registered @dataset_collector and @dataset_cleaner functions for UNODC_PRIPOP (see unodc_pripop cases)",
                        f"{module.__name__}.compute_prison (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                        f"{module.__name__}.impute_prison (unwrapped view function, collection handles stubbed, legacy insert validation applied, impute_reference_class_average observed)",
                    ],
                    fixture,
                ),
                "indicator_code": "PRISON",
                "formula": f"goalpost(UNODC_PRIPOP, {lg}, {ug})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"].strip(),
                "goalposts": [lg, ug],
                "unit": observed_unit,
                "imputed_unit": imputed_unit,
                "impute_route_exists": True,
                "series_fill": {"order": ["forward", "backward", "interpolate"], "forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year", "series_id": ["CountryCode", "DatasetCode"]},
                "reference_class": calls,
                "observed_scores": records(observed, imputation=True),
                "incomplete_identities": identities(incomplete),
                "imputed_scores": records(imputed, imputation=True),
                "legacy_impute_error": error,
                "legacy_output_conflicts": conflicts,
                "empty_dataset": {"observed_scores": records(empty_observed, imputation=True), "imputed_scores": records(empty_imputed, imputation=True), "legacy_impute_error": empty_error},
                "probe_china_observed": {
                    "added_documents": [[d["CountryCode"], d["Year"], d["Value"]] for d in chinese],
                    "legacy_impute_error": probe_error,
                    "stored_twice": probe_conflicts,
                    "imputed_china_years": sorted(d["Year"] for d in probe_imputed if d["CountryCode"] == "CHN"),
                },
                "score_function_cases": score_cases("PRISON", PRISON_SCORE_FUNCTION_CASES),
            },
        )
        methods = {}
        for d in imputed:
            method = d.get("ImputationMethod") or d["Datasets"][0].get("ImputationMethod")
            methods[method] = methods.get(method, 0) + 1
        print(f"PRISON{suffix}: {len(observed)} observed, {len(imputed)} imputed {methods}, reference {calls}, conflicts {conflicts}; empty: {empty_error}; China probe stores twice: {len(probe_conflicts['observed_and_imputed'])}")

    # ------------------------------------------------------------------- CYBSEC
    if "cybsec" in sections:
        from sspi_flask_app.api.core.datasets import dataset_cleaner_registry, dataset_collector_registry
        from sspi_flask_app.api.datasource import itu as itu_source

        dataset = importlib.import_module("sspi_flask_app.api.core.datasets.itu.itu_cybsec")
        dataset.sspi_metadata = metadata

        def run_dataset(content, directory=None):
            """Collector then cleaner, in ``directory`` (a scratch directory holding ``content`` at the legacy path)."""
            raw = RawCapture()
            itu_source.sspi_raw_api_data = dataset.sspi_raw_api_data = raw
            dataset.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)
            with tempfile.TemporaryDirectory() as scratch, working_directory(directory or scratch):
                if content is not None:
                    os.makedirs("local", exist_ok=True)
                    with open(ITU_LEGACY_PATH, "wb") as fh:
                        fh.write(content)
                collector_error = failure(lambda: list(dataset_collector_registry["ITU_CYBSEC"](username="generator")))
                try:
                    return raw, collector_error, dataset_cleaner_registry["ITU_CYBSEC"](), None
                except Exception as exc:  # noqa: BLE001
                    return raw, collector_error, None, f"{type(exc).__name__}: {exc}"

        pinned_raw, pinned_collector_error, _, pinned_cleaner_error = run_dataset(None, OLD_REPO)
        pinned = {
            "legacy_path": ITU_LEGACY_PATH,
            "legacy_path_exists": os.path.exists(os.path.join(OLD_REPO, ITU_LEGACY_PATH)),
            "committed_path": ITU_COMMITTED_PATH,
            "committed_path_exists": os.path.exists(os.path.join(OLD_REPO, ITU_COMMITTED_PATH)),
            "collector_error_in_legacy_repository": pinned_collector_error,
            "cleaner_error_in_legacy_repository": pinned_cleaner_error,
        }
        assert not pinned["legacy_path_exists"] and pinned["committed_path_exists"] and pinned_collector_error and pinned_cleaner_error and not pinned_raw.inserted, pinned
        def cleaner_rows(content):
            """The documents ``clean_itu_cybsec`` hands the clean collection (before its validation), and the empty cells dropped."""
            import pandas as pd

            with tempfile.TemporaryDirectory() as scratch, working_directory(scratch):
                os.makedirs("local")
                with open(ITU_LEGACY_PATH, "wb") as fh:
                    fh.write(content)
                rows = json.loads(str(itu_source.clean_itu_data(None).to_json(orient="records")))
                melted_rows = len(pd.read_csv(ITU_LEGACY_PATH)) * 5
            for d in rows:
                d["DatasetCode"] = "ITU_CYBSEC"  # as clean_itu_cybsec adds it
            return rows, melted_rows - len(rows)

        module = route_module("cybsec")

        def score(clean_documents):
            module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data", clean_documents), validating("sspi_indicator_data", sspi_indicator_data)
            observed = unwrap(module.compute_cybsec)()
            _, incomplete = outcomes["CYBSEC"]
            return observed, incomplete

        def corrected(rows):
            """The cleaner's own documents with ONLY the approved name correction applied (CYBSEC-1), checked by the legacy
            clean collection's validation, then scored by the legacy compute route."""
            applied = sorted({(d["CountryCode"], ITU_APPROVED_NAME_CORRECTIONS[d["CountryCode"]]) for d in rows if d["CountryCode"] in ITU_APPROVED_NAME_CORRECTIONS})
            documents = [{**d, "CountryCode": ITU_APPROVED_NAME_CORRECTIONS.get(d["CountryCode"], d["CountryCode"])} for d in rows]
            sspi_clean_api_data.validate_documents_format(documents)
            observed, incomplete = score(documents)
            return {"corrections_applied": [list(a) for a in applied], "observations": observation_records(documents)}, {"scores": records(observed, imputation=False), "incomplete_identities": identities(incomplete)}

        if args.real:
            with open(os.path.join(args.real, ITU_REAL), "rb") as fh:
                content = fh.read()
            fixture, out, suffix, variants, corrected_variants = ITU_REAL, os.path.join(args.real, "itu", "golden"), "", {}, {}
        else:
            itu_synthetic = builder("itu")
            with open(os.path.join(NEW_REPO, ITU_SYNTHETIC), "rb") as fh:
                content = fh.read()
            assert content == itu_synthetic.build(), "committed transcription differs from build_synthetic.py"
            fixture, out, suffix = ITU_SYNTHETIC, HERE, "_synthetic"
            variants = {name: run_dataset(itu_synthetic.build(name))[3] for name in itu_synthetic.VARIANTS}
            corrected_variants = {"original_unmatched_names": corrected(cleaner_rows(itu_synthetic.build("original_unmatched_names"))[0])}
        raw, collector_error, cleaned, error = run_dataset(content)
        assert collector_error is None, collector_error
        (raw_document,) = raw.inserted
        cleaner_output, empty = cleaner_rows(content)
        unmatched = sorted({d["CountryCode"] for d in cleaner_output if not (len(d["CountryCode"]) == 3 and d["CountryCode"].isupper())})
        source_correction = corrected(cleaner_output) if error is not None else None  # the original transcription: legacy refused it
        write(
            out,
            f"itu_cybsec{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "sspi_flask_app.api.datasource.itu.load_itu_data_from_local_transcription (registered @dataset_collector for ITU_CYBSEC, raw insert captured)",
                        f"{dataset.__name__}.clean_itu_cybsec (registered @dataset_cleaner, legacy insert validation applied), which calls sspi_flask_app.api.datasource.itu.clean_itu_data",
                        "the cleaner's documents with only the approved CYBSEC-1 name correction applied, checked by the legacy clean collection's validation",
                    ],
                    fixture,
                ),
                "dataset_code": "ITU_CYBSEC",
                "pinned_commit_paths": pinned,
                "raw_source_info": raw_document["Source"],
                "cleaner_reads_raw_document": False,
                "legacy_clean_error": error,
                "observations": observation_records(cleaned) if cleaned is not None else None,
                "cleaner_output_before_validation": sorted(({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaner_output), key=lambda d: (str(d["country_code"]), d["year"])),
                "unmatched_country_names": unmatched,
                "empty_source_values": empty,
                "legacy_document_keys": sorted({k for d in cleaned for k in d}) if cleaned is not None else None,
                "invalid_variants": variants,
                "approved_name_corrections": ITU_APPROVED_NAME_CORRECTIONS,
                "corrected_source": source_correction[0] if source_correction else None,
                "corrected_variants": {name: c[0] for name, c in corrected_variants.items()},
            },
        )
        print(f"ITU_CYBSEC{suffix}: pinned paths {pinned}; clean error {error}; {len(cleaner_output)} cleaner rows, unmatched {unmatched}; variants {variants}; corrected {[n for n in corrected_variants] + (['source'] if source_correction else [])}")

        if cleaned is not None:
            observed, incomplete = score(cleaned)
        else:
            observed, incomplete = None, None
        module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data"), validating("sspi_indicator_data", sspi_indicator_data)
        empty_observed = unwrap(module.compute_cybsec)()
        front = frontmatter("CYBSEC")
        write(
            out,
            f"cybsec{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "registered @dataset_collector and @dataset_cleaner functions for ITU_CYBSEC (see itu_cybsec cases)",
                        f"{module.__name__}.compute_cybsec (unwrapped view function, collection handles stubbed, legacy insert validation applied), on the cleaner's documents and on the approved corrected documents",
                    ],
                    fixture,
                ),
                "indicator_code": "CYBSEC",
                "formula": f"goalpost(ITU_CYBSEC, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"].strip(),
                "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
                "unit": "Index",
                "impute_route_exists": hasattr(module, "impute_cybsec"),
                "scores": records(observed, imputation=False) if observed is not None else None,
                "incomplete_identities": identities(incomplete) if incomplete is not None else None,
                "corrected_source_scores": source_correction[1] if source_correction else None,
                "corrected_variants": {name: c[1] for name, c in corrected_variants.items()},
                "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
                "score_function_cases": score_cases("CYBSEC", CYBSEC_SCORE_FUNCTION_CASES),
            },
        )
        scored = observed if observed is not None else source_correction[1]["scores"]
        print(f"CYBSEC{suffix}: {len(scored)} scores; corrected variants {[(n, len(c[1]['scores'])) for n, c in corrected_variants.items()]}")

    # ------------------------------------------------------------------- SECAPP: what the pinned acquisition does
    if "secapp" in sections and not args.real:
        from bs4 import BeautifulSoup
        from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
        from sspi_flask_app.api.datasource import fsi as fsi_source

        base_url = "https://fragilestatesindex.org/excel/"
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # bs4 warns that the markup looks like a URL: that is the defect being recorded
            discovered = [a.get("href") for a in BeautifulSoup(base_url, "html.parser").find_all("a")]
        with open(os.path.join(OLD_REPO, "datasets", "fsi", "fsi_secapp", "documentation.md")) as fh:
            import yaml

            documented_source = yaml.safe_load(fh.read().split("---")[1])["Source"]
        collector_source = {"OrganizationName": "Fragile States Index", "OrganizationCode": "FSI", "QueryCode": "FSI", "BaseURL": base_url, "URL": "<workbook link>"}  # the literal in collect_fsi_data
        mismatched = sorted(k for k, v in documented_source.items() if collector_source.get(k, None) != v)
        records_ = [
            # synthetic records in the shape the cleaner reads: Year as stored after a Mongo round trip of a pandas Timestamp
            {"Country": "Malaysia", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "120th", "Total": 60.0, "C1: Security Apparatus": 6.25},
            {"Country": "Austria", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "170th", "Total": 25.0, "C1: Security Apparatus": 1.5},
            {"Country": "United States", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "150th", "Total": 35.0, "C1: Security Apparatus": 3.0},
            {"Country": "Somalia", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "1st", "Total": 110.0, "C1: Security Apparatus": 10.0},
            {"Country": "Finland", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "178th", "Total": 15.0, "C1: Security Apparatus": 0.0},
        ]
        description = "The Security Apparatus is a component of the Fragile State Index, which considers the security threats to a state such as bombings, attacks/battle-related deaths, rebel movements, mutinies, coups, or terrorism. It is an index scored between 0 and 10."
        stored_shape_error = failure(lambda: fsi_source.clean_fsi_data([{"Raw": records_}], "FSI_SECAPP", "Index", description))
        cleaned = fsi_source.clean_fsi_data([{"Raw": {"json": records_}}], "FSI_SECAPP", "Index", description)
        cleaner_keys = sorted({k for d in cleaned for k in d})
        dataset = importlib.import_module("sspi_flask_app.api.core.datasets.fsi.fsi_secapp")
        dataset.sspi_raw_api_data, dataset.sspi_metadata = types.SimpleNamespace(fetch_raw_data=lambda source_info: [{"Raw": {"json": records_}}]), metadata
        dataset.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)
        registered_cleaner_error = failure(dataset_cleaner_registry["FSI_SECAPP"])  # the registered cleaner, served the shape it reads
        queried = [{**d, "DatasetCode": "FSI_SECAPP"} for d in cleaned]  # the shape compute_secapp queries, which the pinned cleaner never writes
        cote = records_ + [{"Country": "Cote d'Ivoire", "Year": {"$date": "2019-01-01T00:00:00Z"}, "Rank": "20th", "Total": 90.0, "C1: Security Apparatus": 7.5}]
        cote_cleaned = fsi_source.clean_fsi_data([{"Raw": {"json": cote}}], "FSI_SECAPP", "Index", description)
        validation_error = failure(lambda: sspi_clean_api_data.validate_documents_format([{**d, "DatasetCode": "FSI_SECAPP"} for d in cote_cleaned]))
        module = route_module("secapp")
        module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data", cleaned), validating("sspi_indicator_data", sspi_indicator_data)
        observed_on_cleaner_output = unwrap(module.compute_secapp)()
        module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data", queried), validating("sspi_indicator_data", sspi_indicator_data)
        observed = unwrap(module.compute_secapp)()
        front = frontmatter("SECAPP")
        write(
            HERE,
            "secapp_characterization_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "sspi_flask_app.api.datasource.fsi.collect_fsi_data (its BeautifulSoup call, on what it parses)",
                        "sspi_flask_app.api.datasource.fsi.clean_fsi_data (on the stored shape and on the shape it reads)",
                        f"{module.__name__}.compute_secapp (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                    ],
                    "synthetic records written in this generator (no FSI data)",
                ),
                "indicator_code": "SECAPP",
                "pinned_acquisition_stores_values": False,
                "collector": {"parses": base_url, "links_discovered": discovered},
                "raw_document_shape": {"stored_by_collector": "Raw = list of row records", "read_by_cleaner": "Raw['json'] = list of row records", "cleaner_error_on_stored_shape": stored_shape_error},
                "source_info": {"documented": documented_source, "stored_by_collector": collector_source, "fields_that_differ": mismatched},
                "cleaner_registered": "FSI_SECAPP" in dataset_cleaner_registry,
                "cleaner_document_keys": cleaner_keys,
                "registered_cleaner_error_on_the_shape_it_reads": registered_cleaner_error,
                "compute_route_scores_on_cleaner_output": len(observed_on_cleaner_output),
                "cleaner_output": sorted(({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned), key=lambda d: (d["country_code"], d["year"])),
                "unmatched_name_validation_error": validation_error,
                "formula": f"goalpost(FSI_SECAPP, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
                "unit": observed[0]["Unit"],
                "impute_route_exists": hasattr(module, "impute_secapp"),
                "scores_on_documents_with_dataset_code": records(observed, imputation=False),
                "score_function_cases": score_cases("SECAPP", SECAPP_SCORE_FUNCTION_CASES),
            },
        )
        print(f"SECAPP: links {discovered}; stored-shape error {stored_shape_error}; source fields differ {mismatched}; registered cleaner error {registered_cleaner_error}; unmatched-name error {validation_error}; {len(observed_on_cleaner_output)} scores on cleaner output, {len(observed)} with DatasetCode")

    # ------------------------------------------------------------------- FSI_SECAPP and SECAPP through the approved adapter
    if "secapp" in sections:
        from bson import json_util
        import bson
        import pandas as pd
        from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
        from sspi_flask_app.api.datasource import fsi as fsi_source

        dataset = importlib.import_module("sspi_flask_app.api.core.datasets.fsi.fsi_secapp")
        dataset.sspi_metadata = metadata
        legacy_matcher = fsi_source.get_country_code

        def repaired_matcher(name):
            """The legacy matcher with ONLY the approved FSI repair: surrounding whitespace stripped, five spellings corrected."""
            stripped = name.strip()
            return FSI_APPROVED_NAME_CORRECTIONS.get(stripped) or legacy_matcher(stripped)

        def stored(content):
            """The raw document the working (March 2025) collector stored for one workbook, as MongoDB returns it."""
            records_ = pd.read_excel(io.BytesIO(content)).to_dict(orient="records")
            return json.loads(json_util.dumps(bson.decode(bson.encode({"Raw": {"json": records_}}))))

        def run_cleaner(raw_documents, matcher):
            fsi_source.get_country_code = matcher
            try:
                dataset.sspi_raw_api_data = types.SimpleNamespace(fetch_raw_data=lambda source_info: [json.loads(json.dumps(d)) for d in raw_documents])
                dataset.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)
                registered_error = failure(dataset_cleaner_registry["FSI_SECAPP"])  # the registered cleaner, as pinned
                rows = fsi_source.clean_fsi_data([json.loads(json.dumps(d)) for d in raw_documents], "FSI_SECAPP", "Index", "FSI_SECAPP description")
            finally:
                fsi_source.get_country_code = legacy_matcher
            return registered_error, rows

        def repaired(raw_documents):
            """(A) the pinned cleaner's failure; (B) its own rows with only the approved repair; (C) the compute route on them."""
            legacy_error, legacy_rows = run_cleaner(raw_documents, legacy_matcher)
            _, rows = run_cleaner(raw_documents, repaired_matcher)
            documents = [{**d, "DatasetCode": "FSI_SECAPP"} for d in rows]  # the repair: the cleaner never set it
            sspi_clean_api_data.validate_documents_format(documents)
            module = route_module("secapp")
            module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data", documents), validating("sspi_indicator_data", sspi_indicator_data)
            observed = unwrap(module.compute_secapp)()
            _, incomplete = outcomes["SECAPP"]
            return legacy_error, legacy_rows, documents, observed, incomplete

        if args.real:
            fsi_dir = os.path.join(args.real, "fsi")
            names = sorted((f for f in os.listdir(fsi_dir) if f.lower().endswith(".xlsx")), key=str.lower)
            editions = [(int(re.search(r"(\d{4})", f).group(1)), os.path.join(fsi_dir, f)) for f in names]
            fixture, out, suffix, variants = "fsi/*.xlsx (the 18 pinned editions)", os.path.join(fsi_dir, "golden"), "", {}
        else:
            fsi_synthetic = builder("fsi")
            editions = [(e, os.path.join(NEW_REPO, "tests", "fixtures", "fsi", fsi_synthetic.file_name(e))) for e in fsi_synthetic.EDITIONS]
            for edition, path in editions:
                with open(path, "rb") as fh:
                    assert fsi_synthetic.cells(fh.read()) == fsi_synthetic.cells(fsi_synthetic.build(edition)), f"committed {path} differs from build_synthetic.py"
            fixture, out, suffix = [f"tests/fixtures/fsi/{fsi_synthetic.file_name(e)}" for e, _ in editions], HERE, "_synthetic"
            variants = {}
            for variant in fsi_synthetic.VARIANTS:
                raw_variant = [stored(fsi_synthetic.build(e, variant if e == 2021 else None)) for e, _ in editions]
                legacy_error, _ = run_cleaner(raw_variant, legacy_matcher)
                _, rows = run_cleaner(raw_variant, repaired_matcher)
                variants[variant] = {"legacy_error": legacy_error, "repaired_validation_error": failure(lambda: sspi_clean_api_data.validate_documents_format([{**d, "DatasetCode": "FSI_SECAPP"} for d in rows]))}
        raw_documents = []
        for edition, path in editions:
            with open(path, "rb") as fh:
                raw_documents.append(stored(fh.read()))
        legacy_error, legacy_rows, documents, observed, incomplete = repaired(raw_documents)
        edition_years = {}
        for (edition, path), raw_document in zip(editions, raw_documents, strict=True):
            cells = {(c["$date"].split("-")[0] if isinstance(c, dict) else c) for c in (r["Year"] for r in raw_document["Raw"]["json"])}
            edition_years[str(edition)] = {"file": os.path.basename(path), "year_cells": sorted(str(c) for c in cells), "rows": len(raw_document["Raw"]["json"])}
        unmatched = sorted({(d["CountryCode"], d["Year"]) for d in legacy_rows if not (len(d["CountryCode"]) == 3 and d["CountryCode"].isupper())})
        counts = {}
        for d in legacy_rows:
            counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
        write(
            out,
            f"fsi_secapp{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "the March 2025 collector's raw document per workbook (read_excel records under Raw.json, round-tripped through BSON and json_util as MongoDB stored and returned it)",
                        f"{dataset.__name__}.clean_fsi_secapp (registered @dataset_cleaner, legacy insert validation applied): the pinned failure",
                        "sspi_flask_app.api.datasource.fsi.clean_fsi_data with ONLY the approved FSI repair (whitespace stripped, five spellings corrected) and the dataset code added, checked by the legacy clean collection's validation",
                    ],
                    fixture,
                ),
                "dataset_code": "FSI_SECAPP",
                "approved_name_corrections": FSI_APPROVED_NAME_CORRECTIONS,
                "edition_years": edition_years,
                "legacy_clean_error": legacy_error,
                "legacy_unmatched_names": [list(u) for u in unmatched],
                "legacy_duplicate_identities": [list(k) for k, n in sorted(counts.items()) if n > 1],
                "cleaner_output_before_validation": sorted(({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in legacy_rows), key=lambda d: (str(d["country_code"]), d["year"], d["value"])),
                "observations": observation_records(documents),
                "legacy_document_keys": sorted({k for d in legacy_rows for k in d}),
                "invalid_variants": variants,
            },
        )
        front = frontmatter("SECAPP")
        module = route_module("secapp")
        module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data"), validating("sspi_indicator_data", sspi_indicator_data)
        empty_observed = unwrap(module.compute_secapp)()
        write(
            out,
            f"secapp{suffix}_cases.json",
            {
                "generated_from": generated_from(["see fsi_secapp cases", "sspi_flask_app.api.core.sspi.pg.saf.secapp.compute_secapp (unwrapped view function, collection handles stubbed, legacy insert validation applied), on the repaired documents"], fixture),
                "indicator_code": "SECAPP",
                "formula": f"goalpost(FSI_SECAPP, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"].strip(),
                "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
                "unit": "Index",
                "impute_route_exists": hasattr(module, "impute_secapp"),
                "scores": records(observed, imputation=False),
                "incomplete_identities": identities(incomplete),
                "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
                "score_function_cases": score_cases("SECAPP", SECAPP_SCORE_FUNCTION_CASES),
            },
        )
        print(f"FSI_SECAPP{suffix}: {len(raw_documents)} editions, legacy error {legacy_error}; unmatched {len(unmatched)}, duplicates {[k for k, n in counts.items() if n > 1][:3]}; {len(documents)} repaired observations, {len(observed)} SECAPP scores; variants {variants}")


if __name__ == "__main__":
    main()
