"""Generate the Worker Wellbeing golden files from the committed source fixtures:

    unsdg_benfts_unemp_cases.json, unempb_cases.json
    ilo_fatinj_cases.json, fatinj_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_worker_wellbeing_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed fixtures (the UN SDG pivot rows one raw
document each, the ILO SDMX-JSON response as the one raw document the
collector stored); the ``compute_unempb``, ``impute_unempb`` and
``compute_fatinj`` view functions run unwrapped from their decorators with
their collection handles stubbed the same way.

Only UNEMPB and FATINJ are generated. MATERN and SENIOR have no executable
legacy path to record: ``matern.py`` defines no route, no OECD dataset has a
collector or cleaner, and ``compute_senior`` raises at
``sspi_raw_api_data.fetch_raw_data("SENIOR")`` (see
``docs/indicator-migration.md``, Worker Wellbeing indicators not ported).
"""

from __future__ import annotations

import importlib
import json
import math
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import CollectionStub, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub
from generate_worker_engagement_cases import RawTextStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
UNSDG_FIXTURE = "tests/fixtures/unsdg/1_3_1_sample.json"
ILO_FIXTURE = "tests/fixtures/ilo/DF_SDG_F881_SEX_MIG_RT.json"
UNEMPB_SERIES, UNEMPB_DIMENSIONS = "SI_COV_UEMP", {"sex": "BOTHSEX"}  # unsdg_benfts_unemp.py
FATINJ_DIMENSIONS = {"SEX": "SEX_T", "MIG": "MIG_STATUS_TOTAL"}  # ilo_fatinj.py
REFERENCE_CLASS = ("ISL",)  # impute_reference_class_average calls in impute_unempb


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "ms", "wwb", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, organization):
        self.organization = organization

    def get_source_info(self, code):
        return {"OrganizationCode": self.organization}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def output_conflicts(observed, imputed):
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    return {
        "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
        "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
    }


def main() -> None:
    from pycountry import countries
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixture": fixture,
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    def stub_route_module(name, clean, metadata):
        module = importlib.import_module(name)
        collections = {"clean": CollectionStub(clean), "indicator": CollectionStub(), "imputed": CollectionStub()}
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = metadata, collections["clean"]
        module.sspi_indicator_data = collections["indicator"]
        if hasattr(module, "sspi_imputed_data"):
            module.sspi_imputed_data = collections["imputed"]
        return module, collections

    # ------------------------------------------------------------------ UNSDG_BENFTS_UNEMP
    with open(os.path.join(NEW_REPO, UNSDG_FIXTURE)) as fh:
        fixture = json.load(fh)
    unsdg_metadata = MetadataStub("UNSDG")
    cleaner_module = importlib.import_module("sspi_flask_app.api.core.datasets.unsdg.unsdg_benfts_unemp")
    cleaner_module.sspi_raw_api_data = RawStub(fixture["data"])
    cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), unsdg_metadata
    unemp_clean = dataset_cleaner_registry["UNSDG_BENFTS_UNEMP"]()
    assert unemp_clean and all(d["DatasetCode"] == "UNSDG_BENFTS_UNEMP" for d in unemp_clean)

    def iso(code):
        c = countries.get(numeric=f"{int(code):03d}")
        return c.alpha_3 if c else None

    def is_missing(value):
        if value in (None, ""):
            return True
        try:
            return math.isnan(float(value))
        except ValueError:
            return False

    selected = [r for r in fixture["data"] if r["series"] == UNEMPB_SERIES and all(r.get(k) == v for k, v in UNEMPB_DIMENSIONS.items())]
    skipped = sorted({(r["geoAreaCode"], r["geoAreaName"]) for r in selected if iso(r["geoAreaCode"]) is None})
    missing = sum(1 for r in selected if iso(r["geoAreaCode"]) for e in json.loads(r["years"]) if is_missing(e["value"]))
    observations = observation_records(unemp_clean)
    write(
        "unsdg_benfts_unemp_cases.json",
        {
            "generated_from": generated_from([f"{cleaner_module.__name__}.clean_unsdg_benfts_unemp (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.unsdg.extract_sdg, filter_sdg"], UNSDG_FIXTURE),
            "dataset_code": "UNSDG_BENFTS_UNEMP",
            "series_code": UNEMPB_SERIES,
            "dimensions": UNEMPB_DIMENSIONS,
            "observations": observations,
            "skipped_areas": [list(s) for s in skipped],
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in unemp_clean for k in d}),
        },
    )
    years = [o["year"] for o in observations]
    print(f"UNSDG_BENFTS_UNEMP: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values")

    # ------------------------------------------------------------------ UNEMPB
    module, collections = stub_route_module("sspi_flask_app.api.core.sspi.ms.wwb.unempb", unemp_clean, unsdg_metadata)
    observed = unwrap(module.compute_unempb)()
    imputed = unwrap(module.impute_unempb)()
    front = frontmatter("UNEMPB")
    lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
    (observed_unit,) = {d["Unit"] for d in observed}
    (imputed_unit,) = {d["Unit"] for d in imputed}
    values = [d["Value"] for d in unemp_clean]
    case = {
        "generated_from": generated_from(
            [
                "registered @dataset_cleaner function for UNSDG_BENFTS_UNEMP (Mongo handles stubbed)",
                f"{module.__name__}.compute_unempb (unwrapped view function, collection handles stubbed)",
                f"{module.__name__}.impute_unempb (unwrapped view function, collection handles stubbed)",
            ],
            UNSDG_FIXTURE,
        ),
        "indicator_code": "UNEMPB",
        "formula": f"goalpost(UNSDG_BENFTS_UNEMP, {lg:g}, {ug:g})",
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
        "legacy_output_conflicts": output_conflicts(observed, imputed),
    }
    fill_years = [d["Year"] for d in imputed]
    print(
        f"UNEMPB: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), "
        f"{len(imputed)} imputed ({min(fill_years)}-{max(fill_years)}, unit {imputed_unit!r}), "
        f"reference mean {sum(values) / len(values)!r} over {len(values)} rows"
    )
    module, collections = stub_route_module("sspi_flask_app.api.core.sspi.ms.wwb.unempb", [], unsdg_metadata)  # nothing ingested
    empty_observed = unwrap(module.compute_unempb)()
    try:
        unwrap(module.impute_unempb)()
        empty_error = None
    except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
        empty_error = f"{type(exc).__name__}: {exc}"
    case["empty_dataset"] = {"observed_scores": records(empty_observed, imputation=True), "legacy_impute_error": empty_error}
    write("unempb_cases.json", case)
    print(f"UNEMPB on an empty dataset: {len(empty_observed)} observed, impute route: {empty_error}")

    # ------------------------------------------------------------------ ILO_FATINJ
    with open(os.path.join(NEW_REPO, ILO_FIXTURE), encoding="utf-8") as fh:
        text = fh.read()
    message = json.loads(text)
    structure = message["data"]["structures"][0]
    ilo_metadata = MetadataStub("ILO")
    cleaner_module = importlib.import_module("sspi_flask_app.api.core.datasets.ilo.ilo_fatinj")
    cleaner_module.sspi_raw_api_data = RawTextStub(text)
    cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), ilo_metadata
    fatinj_clean = dataset_cleaner_registry["ILO_FATINJ"]()
    assert fatinj_clean and all(d["DatasetCode"] == "ILO_FATINJ" for d in fatinj_clean)
    observations = observation_records(fatinj_clean)
    null_values = sum(1 for data_set in message["data"]["dataSets"] for series in data_set["series"].values() for cells in series["observations"].values() if not cells or cells[0] is None)
    area_codes = [v["id"] for d in structure["dimensions"]["series"] if d["id"] == "REF_AREA" for v in d["values"]]
    write(
        "ilo_fatinj_cases.json",
        {
            "generated_from": generated_from([f"{cleaner_module.__name__}.clean_ilo_fatinj (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.ilo.extract_ilo, parse_sdmx_json_to_tabular, filter_ilo"], ILO_FIXTURE),
            "dataset_code": "ILO_FATINJ",
            "source_request": {"dataflow": "DF_SDG_F881_SEX_MIG_RT", "key": "", "url_params": []},
            "dimensions": FATINJ_DIMENSIONS,
            "series_dimensions": {d["id"]: [v["id"] for v in d["values"]] for d in structure["dimensions"]["series"] if d["id"] != "REF_AREA"},
            "observations": observations,
            "skipped_areas": sorted(code for code in area_codes if any(ch.isdigit() for ch in code)),
            "empty_source_values": null_values,
            "legacy_document_keys": sorted({k for d in fatinj_clean for k in d}),
        },
    )
    years = [o["year"] for o in observations]
    print(f"ILO_FATINJ: {len(observations)} observations, {len({o['country_code'] for o in observations})} areas, {min(years)}-{max(years)}, {null_values} null values")

    # ------------------------------------------------------------------ FATINJ
    module, collections = stub_route_module("sspi_flask_app.api.core.sspi.ms.wwb.fatinj", fatinj_clean, ilo_metadata)
    observed = unwrap(module.compute_fatinj)()
    front = frontmatter("FATINJ")
    lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
    (observed_unit,) = {d["Unit"] for d in observed}
    impute_routes = sorted(name for name in dir(module) if name.startswith("impute_"))
    module, collections = stub_route_module("sspi_flask_app.api.core.sspi.ms.wwb.fatinj", [], ilo_metadata)
    empty_observed = unwrap(module.compute_fatinj)()
    write(
        "fatinj_cases.json",
        {
            "generated_from": generated_from(
                ["registered @dataset_cleaner function for ILO_FATINJ (Mongo handles stubbed)", f"{module.__name__}.compute_fatinj (unwrapped view function, collection handles stubbed)"],
                ILO_FIXTURE,
            ),
            "indicator_code": "FATINJ",
            "formula": f"goalpost(ILO_FATINJ, {lg:g}, {ug:g})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [lg, ug],
            "unit": observed_unit,
            "impute_route_exists": bool(impute_routes),
            "observed_scores": records(observed, imputation=False),
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
        },
    )
    print(f"FATINJ: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), impute routes in module: {impute_routes}")
    print(f"from {commit}")


if __name__ == "__main__":
    main()
