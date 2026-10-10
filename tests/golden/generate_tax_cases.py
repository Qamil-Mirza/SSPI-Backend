"""Generate the Tax golden files from the committed source fixtures:

    wb_taxrev_cases.json, taxrev_cases.json
    wid_nincsh_posttax_equalsplit_p0p50_cases.json
    wid_nincsh_posttax_equalsplit_p90p100_cases.json
    txrdst_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_tax_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed source fixtures (the World Bank rows
one raw document each, the WID country files by name); the
``compute_taxrev``, ``impute_taxrev`` and ``compute_txrdst`` view functions
run unwrapped from their decorators with their collection handles stubbed
the same way.

TXRDST's score function is a closure inside ``compute_txrdst``. It is
observed, not copied: ``score_indicator`` is wrapped to record the
function the route passes, and that legacy function is then evaluated on a
few synthetic share combinations no fixture holds (a zero pre-tax bottom
share, a zero top share, the goalpost boundaries), recording its result or
the exception it raises.

The two pre-tax WID datasets are re-cleaned from the same (extended)
fixture and must equal the committed ``wid_nincsh_pretax_*_cases.json``
observations, which this script does not rewrite.

Sections can be generated separately (``crptax``, ``taxrev-txrdst``; default
both), so adding one indicator does not rewrite the other golden files:

    ... generate_tax_cases.py crptax

CRPTAX: the legacy collector ``collect_tax_foundation_data`` runs with
``requests.get`` answering from the committed fixture the way ``requests``
answered from the server (status 200, ``text`` decoded as ISO-8859-1, since
the server sends ``text/csv`` without a charset), and its raw insert
captured; the registered cleaner then reads that captured document, and the
``compute_crptax`` / ``impute_crptax`` view functions run unwrapped.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import types
from datetime import datetime, timezone

from generate_education_cases import skipped_and_missing, source_rows
from generate_inequality_cases import WID_FIXTURE, CollectionStub, WIDRawStub, identities, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
WB_FIXTURE = "tests/fixtures/wb/GC.TAX.TOTL.GD.ZS_sample.json"
POSTTAX = {"WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50": "p0p50", "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100": "p90p100"}
PRETAX = {"WID_NINCSH_PRETAX_P0P50": "p0p50", "WID_NINCSH_PRETAX_P90P100": "p90p100"}
POSTTAX_VARIABLE = "sdiincj992"
REFERENCE_CLASS = ("VNM", "NGA", "VEN", "DZA")  # impute_reference_class_average calls in impute_taxrev, in order
SECTIONS = ("crptax", "taxrev-txrdst")
TF_FIXTURE = "tests/fixtures/taxfoundation/rates_final_2025-01_sample.csv"
TF_URL = "https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv"  # the legacy collector's literal
# Clean rows removed for the incomplete-group variant: (dataset, country, year)
TXRDST_REMOVED = {
    ("WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50", "MYS", 2005),
    ("WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100", "USA", 2024),
    ("WID_NINCSH_PRETAX_P0P50", "AUT", 2000),
    ("WID_NINCSH_PRETAX_P90P100", "AUT", 2000),
    ("WID_NINCSH_PRETAX_P90P100", "AUT", 2001),
}
# (post-tax bottom 50%, post-tax top 10%, pre-tax bottom 50%, pre-tax top 10%) handed to the legacy closure
SCORE_FUNCTION_CASES = (
    ("typical", 0.20, 0.35, 0.15, 0.45),
    ("no redistribution", 0.15, 0.45, 0.15, 0.45),
    ("ratio falls by exactly 10%", 0.135, 0.45, 0.15, 0.45),
    ("ratio falls by more than 10%", 0.10, 0.45, 0.15, 0.45),
    ("ratio exactly doubles", 0.30, 0.45, 0.15, 0.45),
    ("ratio more than doubles", 0.40, 0.30, 0.15, 0.45),
    ("zero pre-tax bottom share", 0.20, 0.35, 0.0, 0.45),
    ("zero post-tax bottom share", 0.0, 0.35, 0.15, 0.45),
    ("zero post-tax top share", 0.20, 0.0, 0.15, 0.45),
    ("zero pre-tax top share", 0.20, 0.35, 0.15, 0.0),
)


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "ms", "tax", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def generate_crptax(generated_from, write, metadata, logger) -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.datasource import taxfoundation as tf_source

    with open(os.path.join(NEW_REPO, TF_FIXTURE), "rb") as fh:
        content = fh.read()
    requested, stored = [], []

    class Response:
        status_code = 200
        text = content.decode("iso-8859-1")  # requests' decoding of a text/* body with no charset

    def get(url, *args, **kwargs):
        requested.append(url)
        return Response()

    class RawRecorder:
        def raw_insert_one(self, document, source_info, **kwargs):
            assert kwargs.get("username") is not None
            stored.append({"Raw": document, "Source": dict(source_info)})
            return 1

        def fetch_raw_data(self, source_info):
            return [dict(d) for d in stored if all(d["Source"].get(k) == v for k, v in source_info.items())]

    tf_source.requests = types.SimpleNamespace(get=get)
    tf_source.sspi_raw_api_data = RawRecorder()
    messages = list(tf_source.collect_tax_foundation_data(username="golden"))
    assert requested == [TF_URL] and len(stored) == 1, (requested, messages)
    source_info = stored[0]["Source"]

    cleaner_module = importlib.import_module("sspi_flask_app.api.core.datasets.tf.tf_crptax")
    cleaner_module.sspi_raw_api_data = tf_source.sspi_raw_api_data
    cleaner_module.sspi_clean_api_data = CleanStub()
    cleaner_module.sspi_metadata = types.SimpleNamespace(get_source_info=lambda code: {"OrganizationCode": "TF", "QueryCode": "rates_final"}, record_dataset_range=lambda documents, code: None)
    cleaned = dataset_cleaner_registry["TF_CRPTAX"]()
    assert cleaned and all(d["DatasetCode"] == "TF_CRPTAX" for d in cleaned)
    observations = observation_records(cleaned)
    import csv
    import io

    table = list(csv.reader(io.StringIO(content.decode("utf-8"), newline="")))
    header, body = table[0], table[1:]
    year_positions = [i for i, name in enumerate(header) if name.isdigit()]
    missing = sum(1 for row in body for i in year_positions if row[i] == "NA")
    write(
        "tf_crptax_cases.json",
        {
            "generated_from": generated_from(
                [
                    "sspi_flask_app.api.datasource.taxfoundation.collect_tax_foundation_data (requests.get answered from the fixture, raw insert captured)",
                    "sspi_flask_app.api.core.datasets.tf.tf_crptax.clean_tf_crptax (registered @dataset_cleaner, Mongo handles stubbed)",
                    "sspi_flask_app.api.datasource.taxfoundation.clean_tax_foundation",
                ],
                fixture=TF_FIXTURE,
            ),
            "dataset_code": "TF_CRPTAX",
            "source_url": requested[0],
            "legacy_source_info": source_info,
            "source_rows": len(body),
            "source_years": [int(header[year_positions[0]]), int(header[year_positions[-1]])],
            "observations": observations,
            "descriptions": sorted({d["Description"] for d in cleaned}),
            "skipped_areas": [],
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in cleaned for k in d}),
        },
    )
    years = [o["year"] for o in observations]
    print(f"TF_CRPTAX: {len(observations)} observations, {len({o['country_code'] for o in observations})} areas, {min(years)}-{max(years)}, {missing} missing values")

    clean_collection, indicator_data, imputed_data = CollectionStub(cleaned), CollectionStub(), CollectionStub()
    module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.tax.crptax")
    module.app, module.parse_json = logger, lambda value: value
    module.sspi_metadata, module.sspi_clean_api_data = metadata, clean_collection
    module.sspi_indicator_data, module.sspi_imputed_data = indicator_data, imputed_data
    observed = unwrap(module.compute_crptax)()
    imputed = unwrap(module.impute_crptax)()
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    module.sspi_clean_api_data = CollectionStub()  # nothing ingested
    empty = {"observed_scores": records(unwrap(module.compute_crptax)(), imputation=True)}
    try:
        empty["imputed_scores"] = records(unwrap(module.impute_crptax)(), imputation=True)
        empty["legacy_impute_error"] = None
    except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
        empty["imputed_scores"], empty["legacy_impute_error"] = None, f"{type(exc).__name__}: {exc}"
    front = frontmatter("CRPTAX")
    lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
    (observed_unit,) = {d["Unit"] for d in observed}
    (imputed_unit,) = {d["Unit"] for d in imputed}
    write(
        "crptax_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner function for TF_CRPTAX, fed by the legacy collector (Mongo handles stubbed)",
                    f"{module.__name__}.compute_crptax (unwrapped view function, collection handles stubbed)",
                    f"{module.__name__}.impute_crptax (unwrapped view function, collection handles stubbed)",
                ],
                fixture=TF_FIXTURE,
            ),
            "indicator_code": "CRPTAX",
            "formula": f"goalpost(TF_CRPTAX, {lg:g}, {ug:g})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [lg, ug],
            "unit": observed_unit,
            "imputed_unit": imputed_unit,
            "impute_route_exists": True,
            "series_fill": {"backward_to": 2000, "forward_to": None, "interpolation": "every interior gap, any year"},
            "observed_scores": records(observed, imputation=True),
            "imputed_scores": records(imputed, imputation=True),
            "empty_dataset": empty,
            "legacy_impute_error": None,
            "legacy_output_conflicts": {
                "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
                "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
            },
        },
    )
    fill_years = [d["Year"] for d in imputed]
    print(
        f"CRPTAX: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), "
        f"{len(imputed)} imputed ({min(fill_years)}-{max(fill_years)}, unit {imputed_unit!r}), {len(observed_ids & set(counts))} identities both observed and imputed; "
        f"empty dataset: {empty}"
    )


def main(sections=SECTIONS) -> None:
    from pycountry import countries
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.datasource import wid as wid_source

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        metadata = MetadataStub(json.load(fh))
    warnings = []
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda message, *a, **k: warnings.append(message)))

    def generated_from(functions, **fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            **fixture,
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    if "crptax" in sections:
        generate_crptax(generated_from, write, metadata, logger)

    if "taxrev-txrdst" in sections:
        # ------------------------------------------------------------ WB_TAXREV
        rows = source_rows("WB", WB_FIXTURE)
        wb_module = importlib.import_module("sspi_flask_app.api.core.datasets.wb.wb_taxrev")
        wb_module.sspi_raw_api_data = RawStub(rows)
        wb_module.sspi_clean_api_data, wb_module.sspi_metadata = CleanStub(), metadata
        taxrev_clean = dataset_cleaner_registry["WB_TAXREV"]()
        assert taxrev_clean and all(d["DatasetCode"] == "WB_TAXREV" for d in taxrev_clean)
        skipped, missing = skipped_and_missing("WB", rows)
        observations = observation_records(taxrev_clean)
        write(
            "wb_taxrev_cases.json",
            {
                "generated_from": generated_from(
                    ["sspi_flask_app.api.core.datasets.wb.wb_taxrev.clean_wb_taxrev (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"],
                    fixture=WB_FIXTURE,
                ),
                "dataset_code": "WB_TAXREV",
                "source_indicator": "GC.TAX.TOTL.GD.ZS",
                "observations": observations,
                "descriptions": sorted({d["Description"] for d in taxrev_clean}),
                "skipped_areas": skipped,
                "empty_source_values": missing,
                "legacy_document_keys": sorted({k for d in taxrev_clean for k in d}),
            },
        )
        years = [o["year"] for o in observations]
        print(f"WB_TAXREV: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values")

        # --------------------------------------------------------------- TAXREV
        clean_collection, indicator_data, imputed_data = CollectionStub(taxrev_clean), CollectionStub(), CollectionStub()
        module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.tax.taxrev")
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = metadata, clean_collection
        module.sspi_indicator_data, module.sspi_imputed_data = indicator_data, imputed_data
        observed = unwrap(module.compute_taxrev)()
        imputed = unwrap(module.impute_taxrev)()
        observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
        counts = {}
        for d in imputed:
            counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
        front = frontmatter("TAXREV")
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (observed_unit,) = {d["Unit"] for d in observed}
        (imputed_unit,) = {d["Unit"] for d in imputed}
        values = [d["Value"] for d in taxrev_clean]
        write(
            "taxrev_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "registered @dataset_cleaner function for WB_TAXREV (Mongo handles stubbed)",
                        f"{module.__name__}.compute_taxrev (unwrapped view function, collection handles stubbed)",
                        f"{module.__name__}.impute_taxrev (unwrapped view function, collection handles stubbed)",
                    ],
                    fixture=WB_FIXTURE,
                ),
                "indicator_code": "TAXREV",
                "formula": f"goalpost(WB_TAXREV, {lg:g}, {ug:g})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"],
                "goalposts": [lg, ug],
                "unit": observed_unit,
                "imputed_unit": imputed_unit,
                "impute_route_exists": True,
                "series_fill": {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"},
                "reference_class": {"recipients": list(REFERENCE_CLASS), "years": [2000, 2023], "reference": "every clean row of the dataset, all countries and years", "reference_count": len(values), "mean": sum(values) / len(values)},
                "observed_scores": records(observed, imputation=True),
                "imputed_scores": records(imputed, imputation=True),
                "legacy_impute_error": None,
                "legacy_output_conflicts": {
                    "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
                    "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
                },
            },
        )
        fill_years = [d["Year"] for d in imputed]
        module.sspi_clean_api_data = CollectionStub()  # nothing ingested
        empty_observed = unwrap(module.compute_taxrev)()
        try:
            unwrap(module.impute_taxrev)()
            empty_error = None
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            empty_error = f"{type(exc).__name__}: {exc}"
        with open(os.path.join(HERE, "taxrev_cases.json")) as fh:
            case = json.load(fh)
        case["empty_dataset"] = {"observed_scores": records(empty_observed, imputation=True), "legacy_impute_error": empty_error}
        write("taxrev_cases.json", case)
        print(
            f"TAXREV: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), "
            f"{len(imputed)} imputed ({min(fill_years)}-{max(fill_years)}, unit {imputed_unit!r}), {len(observed_ids & set(counts))} identities both observed and imputed, "
            f"reference mean {sum(values) / len(values)!r} over {len(values)} rows"
        )

        # ------------------------------------------------------------------ WID
        wid_source.sspi_raw_api_data = WIDRawStub()
        clean = {}
        for dataset, percentile in {**POSTTAX, **PRETAX}.items():
            cleaner_module = importlib.import_module(f"sspi_flask_app.api.core.datasets.wid.{dataset.lower()}")
            cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), metadata
            cleaned = dataset_cleaner_registry[dataset]()
            assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
            clean[dataset] = cleaned
            observations = observation_records(cleaned)
            if dataset in PRETAX:  # the committed ISHRAT-era goldens must still describe this fixture
                with open(os.path.join(HERE, f"{dataset.lower()}_cases.json")) as fh:
                    assert json.load(fh)["observations"] == observations, f"{dataset}: the extended fixture changed the legacy pre-tax output"
                print(f"{dataset}: {len(observations)} observations, identical to the committed golden file")
                continue
            published = {}
            for code in sorted({d["CountryCode"] for d in cleaned}):
                with open(os.path.join(NEW_REPO, WID_FIXTURE, f"WID_data_{countries.get(alpha_3=code).alpha_2}.csv"), encoding="utf-8") as fh:
                    for line in fh:
                        parts = line.rstrip("\n").split(";")
                        if parts[1] == POSTTAX_VARIABLE and parts[2] == percentile:
                            published[(code, int(parts[3]))] = parts[4]
            write(
                f"{dataset.lower()}_cases.json",
                {
                    "generated_from": generated_from(
                        [f"{cleaner_module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.wid.filter_wid_csv"],
                        fixture=WID_FIXTURE,
                    ),
                    "dataset_code": dataset,
                    "source_selection": {"archive": "wid_all_data", "variable": POSTTAX_VARIABLE, "percentile": percentile, "years": [2000, 2024], "country_group": "SSPI67"},
                    "observations": observations,
                    "published_values": [{"country_code": o["country_code"], "year": o["year"], "published": published[(o["country_code"], o["year"])]} for o in observations],
                    "legacy_document_keys": sorted({k for d in cleaned for k in d}),
                },
            )
            years = [o["year"] for o in observations]
            differing = sum(1 for o in observations if float(published[(o["country_code"], o["year"])]) != o["value"])
            print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {differing} values differ from the published decimal (float32)")

        # --------------------------------------------------------------- TXRDST
        indicator_data, incomplete_data = CollectionStub(), CollectionStub()
        clean_collection = CollectionStub([d for code in clean for d in clean[code]])
        txrdst_module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.tax.txrdst")
        txrdst_module.app, txrdst_module.parse_json = logger, lambda value: value
        txrdst_module.sspi_metadata, txrdst_module.sspi_clean_api_data = metadata, clean_collection
        txrdst_module.sspi_indicator_data, txrdst_module.sspi_incomplete_indicator_data = indicator_data, incomplete_data
        passed = []
        legacy_score_indicator = txrdst_module.score_indicator

        def recording_score_indicator(*args, **kwargs):
            passed.append(kwargs["score_function"])
            return legacy_score_indicator(*args, **kwargs)

        txrdst_module.score_indicator = recording_score_indicator
        scored = unwrap(txrdst_module.compute_txrdst)()
        assert len(passed) == 1 and not warnings, warnings
        (score_function,) = passed
        parameters = list(score_function.__code__.co_varnames[: score_function.__code__.co_argcount])
        function_cases = []
        for label, post_bottom, post_top, pre_bottom, pre_top in SCORE_FUNCTION_CASES:
            inputs = {"WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50": post_bottom, "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100": post_top, "WID_NINCSH_PRETAX_P0P50": pre_bottom, "WID_NINCSH_PRETAX_P90P100": pre_top}
            before = len(warnings)
            try:
                outcome = {"score": score_function(**inputs), "error": None}
            except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
                outcome = {"score": None, "error": type(exc).__name__}
            function_cases.append({"case": label, "inputs": inputs, **outcome, "warnings": warnings[before:]})
        front = frontmatter("TXRDST")
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        write(
            "txrdst_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"registered @dataset_cleaner functions for {', '.join(clean)} (Mongo handles stubbed)",
                        "sspi_flask_app.api.core.sspi.ms.tax.txrdst.compute_txrdst (unwrapped view function, collection handles stubbed)",
                        "the score_txrdst closure compute_txrdst passed to score_indicator (recorded, then evaluated on synthetic inputs)",
                    ],
                    fixture=WID_FIXTURE,
                ),
                "indicator_code": "TXRDST",
                "formula": f"goalpost((posttax_ratio - pretax_ratio) / pretax_ratio * 100, {lg:g}, {ug:g})",
                "methodology_score_function": " ".join(front["ScoreFunction"].split()),
                "methodology_description": " ".join(front["Description"].split()),
                "goalposts": [lg, ug],
                "score_function_parameters": parameters,
                "unit": scored[0]["Unit"],
                "impute_route_exists": False,
                "scores": records(scored, imputation=False),
                "incomplete_identities": identities(incomplete_data.documents),
                "score_function_cases": function_cases,
            },
        )
        # Variant: the same route on the clean rows minus a few, so some groups are incomplete
        removed = sorted(TXRDST_REMOVED)
        indicator_data, incomplete_data = CollectionStub(), CollectionStub()
        txrdst_module.sspi_indicator_data, txrdst_module.sspi_incomplete_indicator_data = indicator_data, incomplete_data
        txrdst_module.sspi_clean_api_data = CollectionStub([d for code in clean for d in clean[code] if (d["DatasetCode"], d["CountryCode"], d["Year"]) not in TXRDST_REMOVED])
        variant = unwrap(txrdst_module.compute_txrdst)()
        with open(os.path.join(HERE, "txrdst_cases.json")) as fh:
            case = json.load(fh)
        case["variants"] = [{"name": "with_rows_removed", "removed_observations": [list(r) for r in removed], "scores": records(variant, imputation=False), "incomplete_identities": identities(incomplete_data.documents)}]
        write("txrdst_cases.json", case)
        print(f"TXRDST with {len(removed)} rows removed: {len(variant)} scores, {len(incomplete_data.documents)} incomplete")
        years = [d["Year"] for d in scored]
        print(f"TXRDST: {len(scored)} scores, {len({d['CountryCode'] for d in scored})} countries, {min(years)}-{max(years)}, {len(incomplete_data.documents)} incomplete")
        for case in function_cases:
            print(f"  {case['case']}: {case['score'] if case['error'] is None else case['error']} {case['warnings']}")
    print(f"from {commit}")


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or SECTIONS)
