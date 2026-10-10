"""Generate the Education golden files from the committed source fixtures:

    wb_puptch_cases.json, puptch_cases.json
    uis_enrpri_cases.json, enrpri_cases.json
    uis_enrsec_cases.json, enrsec_cases.json
    uis_yrsedu_cases.json, yrsedu_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_education_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed source rows, one raw document per
row as the legacy collectors stored them (so ``clean_wb_data`` and
``clean_uis_data`` run unchanged); the ``compute_*`` and ``impute_*`` view
functions run unwrapped from their decorators with their collection
handles stubbed the same way.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import CollectionStub, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
UIS_VERSION_FIXTURE = "tests/fixtures/uis/versions_default.json"
CASES = (
    # indicator, dataset, organization, source indicator, fixture, cleaner module
    ("PUPTCH", "WB_PUPTCH", "WB", "SE.PRM.ENRL.TC.ZS", "tests/fixtures/wb/SE.PRM.ENRL.TC.ZS_sample.json", "sspi_flask_app.api.core.datasets.wb.wb_puptch"),
    ("ENRPRI", "UIS_ENRPRI", "UIS", "NERT.1.CP", "tests/fixtures/uis/NERT.1.CP_sample.json", "sspi_flask_app.api.core.datasets.uis.uis_enrpri"),
    ("ENRSEC", "UIS_ENRSEC", "UIS", "NERT.2.CP", "tests/fixtures/uis/NERT.2.CP_sample.json", "sspi_flask_app.api.core.datasets.uis.uis_enrsec"),
    ("YRSEDU", "UIS_YRSEDU", "UIS", "YEARS.FC.COMP.1T3", "tests/fixtures/uis/YEARS.FC.COMP.1T3_sample.json", "sspi_flask_app.api.core.datasets.uis.uis_yrsedu"),
)
SERIES_FILL = {"YRSEDU": {"backward_to": 2000, "forward_to": None, "interpolation": None}}  # the legacy impute route only extrapolates backward
LEGACY_DATASOURCE = {"WB": "sspi_flask_app.api.datasource.worldbank.clean_wb_data", "UIS": "sspi_flask_app.api.datasource.uis.clean_uis_data"}
REFERENCE_CLASS = {"ENRSEC": ("CHN", "NGA")}  # impute_reference_class_average calls in the legacy impute route


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "pg", "edu", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def source_rows(organization, fixture):
    """The rows the legacy collector stored, one raw document each."""
    with open(os.path.join(NEW_REPO, fixture), encoding="utf-8") as fh:
        payload = json.load(fh)
    if organization == "WB":
        _, rows = payload
        return rows
    assert payload["hints"] == [], payload["hints"]
    return payload["records"]


def skipped_and_missing(organization, rows):
    """What the legacy cleaner dropped: areas pycountry does not know, and empty values of known areas."""
    from pycountry import countries

    skipped, missing = {}, 0
    for row in rows:
        if organization == "WB":
            code, name = row["countryiso3code"] or row["country"]["id"], row["country"]["value"]
        else:
            code, name = row["geoUnit"], ""
        if countries.get(alpha_3=code) is None:
            skipped[(code, name)] = None
        elif not row["value"] or row["value"] == "NaN":
            missing += 1
    return [list(s) for s in sorted(skipped)], missing


def main() -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = MetadataStub()
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))
    with open(os.path.join(NEW_REPO, UIS_VERSION_FIXTURE)) as fh:
        uis_version = json.load(fh)["version"]

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

    for indicator, dataset, organization, source_indicator, fixture, cleaner_name in CASES:
        # ------------------------------------------------------------- dataset
        rows = source_rows(organization, fixture)
        cleaner_module = importlib.import_module(cleaner_name)
        cleaner_module.sspi_raw_api_data = RawStub(rows)
        cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        skipped, missing = skipped_and_missing(organization, rows)
        observations = observation_records(cleaned)
        case = {
            "generated_from": generated_from([f"{cleaner_name}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)", LEGACY_DATASOURCE[organization]], fixture),
            "dataset_code": dataset,
            "source_indicator": source_indicator,
            "observations": observations,
            "descriptions": sorted({d["Description"] for d in cleaned}),
            "skipped_areas": skipped,
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in cleaned for k in d}),
        }
        if organization == "UIS":
            case["source_version"] = uis_version  # the release the fixture was downloaded from; the legacy request named none
        write(f"{dataset.lower()}_cases.json", case)
        years = [o["year"] for o in observations]
        print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values")

        # ----------------------------------------------------------- indicator
        clean_collection, indicator_data, imputed_data = CollectionStub(cleaned), CollectionStub(), CollectionStub()
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.pg.edu.{indicator.lower()}")
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = metadata, clean_collection
        module.sspi_indicator_data, module.sspi_imputed_data = indicator_data, imputed_data
        observed = unwrap(getattr(module, f"compute_{indicator.lower()}"))()
        imputed = unwrap(getattr(module, f"impute_{indicator.lower()}"))()
        observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
        counts = {}
        for d in imputed:
            counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
        front = frontmatter(indicator)
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (observed_unit,) = {d["Unit"] for d in observed}
        (imputed_unit,) = {d["Unit"] for d in imputed}
        recipients = REFERENCE_CLASS.get(indicator, ())
        values = [d["Value"] for d in cleaned]
        reference_class = (
            {"reference_class": {"recipients": list(recipients), "years": [2000, 2023], "reference": "every clean row of the dataset, all countries and years", "reference_count": len(values), "mean": sum(values) / len(values)}}
            if recipients
            else {}
        )
        write(
            f"{indicator.lower()}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"registered @dataset_cleaner function for {dataset} (Mongo handles stubbed)",
                        f"{module.__name__}.compute_{indicator.lower()} (unwrapped view function, collection handles stubbed)",
                        f"{module.__name__}.impute_{indicator.lower()} (unwrapped view function, collection handles stubbed)",
                    ],
                    fixture,
                ),
                "indicator_code": indicator,
                "formula": f"goalpost({dataset}, {lg:g}, {ug:g})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"],
                "goalposts": [lg, ug],
                "unit": observed_unit,
                "imputed_unit": imputed_unit,
                "impute_route_exists": True,
                "series_fill": SERIES_FILL.get(indicator, {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"}),
                **reference_class,
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
        print(
            f"{indicator}: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), "
            f"{len(imputed)} imputed ({min(fill_years)}-{max(fill_years)}, unit {imputed_unit!r}), "
            f"{len(observed_ids & set(counts))} identities both observed and imputed"
        )
    print(f"from {commit}")


if __name__ == "__main__":
    main()
