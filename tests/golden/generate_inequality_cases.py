"""Generate the Inequality golden files from the committed source fixtures:

    wid_nincsh_pretax_p0p50_cases.json, wid_nincsh_pretax_p90p100_cases.json
    ishrat_cases.json
    wb_ginipt_cases.json
    ginipt_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_inequality_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed fixture files; the ``compute_ishrat``,
``compute_ginipt`` and ``impute_ginipt`` view functions run unwrapped from
their decorators with their collection handles stubbed the same way, each
reading what the previous one "stored" (the legacy run order: ISHRAT is
computed before GINIPT is imputed).

For the GINIPT regression fallback the legacy ``LinearRegression`` (sklearn)
is observed, not replaced: a recording subclass notes the training frame,
the fitted coefficient and intercept, and the prediction inputs.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import types
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
WID_FIXTURE = "tests/fixtures/wid"
WB_FIXTURE = "tests/fixtures/wb/SI.POV.GINI_sample.json"
WID_DATASETS = {"WID_NINCSH_PRETAX_P90P100": "p90p100", "WID_NINCSH_PRETAX_P0P50": "p0p50"}
WID_VARIABLE = "sptincj992"


def goalposts(code):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "ms", "neq", code.lower(), "methodology.md")) as fh:
        frontmatter = yaml.safe_load(fh.read().split("---")[1])
    return frontmatter["LowerGoalpost"], frontmatter["UpperGoalpost"]


class WIDRawStub:
    """``sspi_raw_api_data`` for the WID datasource: one raw document per archive member, by file name."""

    def fetch_raw_data(self, source_info):
        with open(os.path.join(NEW_REPO, WID_FIXTURE, source_info["Filename"]), encoding="utf-8", newline="") as fh:
            return [{"Raw": fh.read()}]


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"OrganizationCode": code.split("_")[0]}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        return goalposts(code)


class CollectionStub:
    """An in-memory collection answering the queries the three routes make."""

    def __init__(self, documents=()):
        self.documents = list(documents)

    def find(self, query):
        def matches(doc):
            for key, wanted in query.items():
                if isinstance(wanted, dict):
                    (operator, operand), = wanted.items()
                    assert operator == "$nin", wanted
                    if doc.get(key) in operand:
                        return False
                elif doc.get(key) != wanted:
                    return False
            return True

        return [json.loads(json.dumps(d)) for d in self.documents if matches(d)]  # fresh copies, as Mongo would return

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [d for d in self.documents if any(d.get(k) != v for k, v in query.items())]
        return before - len(self.documents)

    def insert_many(self, documents):
        self.documents.extend(json.loads(json.dumps(documents)))
        return len(documents)


def unwrap(route):
    while hasattr(route, "__wrapped__"):
        route = route.__wrapped__
    return route


def slim(d):
    return {
        "dataset_code": d["DatasetCode"],
        "country_code": d["CountryCode"],
        "year": d["Year"],
        "value": d["Value"],
        "unit": d["Unit"],
        "imputed": bool(d.get("Imputed", False)),
        "imputation_method": d.get("ImputationMethod"),
        "imputation_distance": d.get("ImputationDistance"),
    }


def score_record(d, *, imputation):
    record = {
        "country_code": d["CountryCode"],
        "year": d["Year"],
        "score": d["Score"],
        "unit": d["Unit"],
    }
    if imputation:
        record["inputs"] = sorted((slim(x) for x in d.get("Datasets", [])), key=lambda x: x["dataset_code"])
        record.update(imputed=bool(d.get("Imputed", False)), imputation_method=d.get("ImputationMethod"), imputation_distance=d.get("ImputationDistance"))
    else:
        record["inputs"] = sorted(({"dataset_code": x["DatasetCode"], "value": x["Value"], "unit": x["Unit"]} for x in d.get("Datasets", [])), key=lambda x: x["dataset_code"])
    return record


def records(scored, *, imputation):
    return sorted((score_record(d, imputation=imputation) for d in scored), key=lambda d: (d["country_code"], d["year"]))


def identities(docs):
    return [list(i) for i in sorted({(d["CountryCode"], d["Year"]) for d in docs})]


def observation_records(cleaned):
    return sorted(({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned), key=lambda d: (d["country_code"], d["year"]))


def main() -> None:
    import importlib

    import sklearn
    from pycountry import countries
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.datasource import wid as wid_source
    from sspi_flask_app.api.resources import utilities

    from generate_legacy_cleaner_cases import CleanStub, RawStub

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        metadata = MetadataStub(json.load(fh))
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

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

    # ------------------------------------------------------------------ WID
    wid_source.sspi_raw_api_data = WIDRawStub()
    clean = {}
    for dataset, percentile in WID_DATASETS.items():
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.wid.{dataset.lower()}")
        module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        clean[dataset] = cleaned
        observations = observation_records(cleaned)
        published = {}
        for code in sorted({d["CountryCode"] for d in cleaned}):
            with open(os.path.join(NEW_REPO, WID_FIXTURE, f"WID_data_{countries.get(alpha_3=code).alpha_2}.csv"), encoding="utf-8") as fh:
                for line in fh:
                    parts = line.rstrip("\n").split(";")
                    if parts[1] == WID_VARIABLE and parts[2] == percentile:
                        published[(code, int(parts[3]))] = parts[4]
        write(
            f"{dataset.lower()}_cases.json",
            {
                "generated_from": generated_from(
                    [f"{module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.wid.filter_wid_csv"],
                    fixture=WID_FIXTURE,
                ),
                "dataset_code": dataset,
                "source_selection": {"archive": "wid_all_data", "variable": WID_VARIABLE, "percentile": percentile, "years": [2000, 2024], "country_group": "SSPI67"},
                "observations": observations,
                "published_values": [{"country_code": o["country_code"], "year": o["year"], "published": published[(o["country_code"], o["year"])]} for o in observations],
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        years = [o["year"] for o in observations]
        differing = sum(1 for o in observations if float(published[(o["country_code"], o["year"])]) != o["value"])
        print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {differing} values differ from the published decimal (float32)")

    # --------------------------------------------------------------- ISHRAT
    indicator_data, incomplete_data = CollectionStub(), CollectionStub()
    clean_collection = CollectionStub([d for code in WID_DATASETS for d in clean[code]])
    ishrat_module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.neq.ishrat")
    ishrat_module.app, ishrat_module.parse_json = logger, lambda value: value
    ishrat_module.sspi_metadata, ishrat_module.sspi_clean_api_data = metadata, clean_collection
    ishrat_module.sspi_indicator_data, ishrat_module.sspi_incomplete_indicator_data = indicator_data, incomplete_data
    ishrat_scored = unwrap(ishrat_module.compute_ishrat)()
    lg, ug = goalposts("ISHRAT")
    write(
        "ishrat_cases.json",
        {
            "generated_from": generated_from(
                [
                    f"registered @dataset_cleaner functions for {', '.join(WID_DATASETS)} (Mongo handles stubbed)",
                    "sspi_flask_app.api.core.sspi.ms.neq.ishrat.compute_ishrat (unwrapped view function, collection handles stubbed)",
                ],
                fixture=WID_FIXTURE,
            ),
            "indicator_code": "ISHRAT",
            "formula": f"goalpost(WID_NINCSH_PRETAX_P0P50 / WID_NINCSH_PRETAX_P90P100, {lg:g}, {ug:g})",
            "goalposts": [lg, ug],
            "unit": ishrat_scored[0]["Unit"],
            "impute_route_exists": False,
            "scores": records(ishrat_scored, imputation=False),
            "incomplete_identities": identities(incomplete_data.documents),
        },
    )
    years = [d["Year"] for d in ishrat_scored]
    print(f"ISHRAT: {len(ishrat_scored)} scores, {len({d['CountryCode'] for d in ishrat_scored})} countries, {min(years)}-{max(years)}, {len(incomplete_data.documents)} incomplete")

    # ------------------------------------------------------------ WB_GINIPT
    with open(os.path.join(NEW_REPO, WB_FIXTURE)) as fh:
        _, wb_rows = json.load(fh)
    wb_module = importlib.import_module("sspi_flask_app.api.core.datasets.wb.wb_ginipt")
    wb_module.sspi_raw_api_data = RawStub(wb_rows)
    wb_module.sspi_clean_api_data, wb_module.sspi_metadata = CleanStub(), metadata
    wb_clean = dataset_cleaner_registry["WB_GINIPT"]()
    assert wb_clean and all(d["DatasetCode"] == "WB_GINIPT" for d in wb_clean)
    skipped = {}
    missing = 0
    for row in wb_rows:
        code = row["countryiso3code"] or row["country"]["id"]
        if countries.get(alpha_3=code) is None:
            skipped[(code, row["country"]["value"])] = None
        elif not row["value"]:
            missing += 1
    wb_observations = observation_records(wb_clean)
    write(
        "wb_ginipt_cases.json",
        {
            "generated_from": generated_from(
                ["sspi_flask_app.api.core.datasets.wb.wb_ginipt.clean_wb_ginipt (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"],
                fixture=WB_FIXTURE,
            ),
            "dataset_code": "WB_GINIPT",
            "source_indicator": "SI.POV.GINI",
            "observations": wb_observations,
            "descriptions": sorted({d["Description"] for d in wb_clean}),
            "skipped_areas": [list(s) for s in sorted(skipped)],
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in wb_clean for k in d}),
        },
    )
    years = [o["year"] for o in wb_observations]
    print(f"WB_GINIPT: {len(wb_observations)} observations, {len({o['country_code'] for o in wb_observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values")

    # --------------------------------------------------------------- GINIPT
    fits = []

    class RecordingLinearRegression(utilities.LinearRegression):
        def fit(self, X, y, *args, **kwargs):
            fitted = super().fit(X, y, *args, **kwargs)
            fits.append({"model": fitted, "X": X.copy(), "y": y.copy(), "predictions": []})
            return fitted

        def predict(self, X):
            out = super().predict(X)
            fits[-1]["predictions"].append((X.copy(), out.copy()))
            return out

    utilities.LinearRegression = RecordingLinearRegression
    imputed_data = CollectionStub()
    clean_collection.insert_many(wb_clean)
    ginipt_module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.neq.ginipt")
    ginipt_module.app, ginipt_module.parse_json = logger, lambda value: value
    ginipt_module.sspi_metadata, ginipt_module.sspi_clean_api_data = metadata, clean_collection
    ginipt_module.sspi_indicator_data, ginipt_module.sspi_imputed_data = indicator_data, imputed_data
    observed = unwrap(ginipt_module.compute_ginipt)()
    imputed = unwrap(ginipt_module.impute_ginipt)()
    series_fill = [d for d in imputed if "Datasets" in d]
    predicted = [d for d in imputed if "Datasets" not in d]
    assert len(fits) == 1 and len(fits[0]["predictions"]) == 1 and len(series_fill) + len(predicted) == len(imputed)
    fit = fits[0]
    (feature,) = list(fit["X"].columns)
    prediction_frame, prediction_values = fit["predictions"][0]
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    lg, ug = goalposts("GINIPT")
    write(
        "ginipt_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner functions for WB_GINIPT and the two WID datasets (Mongo handles stubbed)",
                    "sspi_flask_app.api.core.sspi.ms.neq.ishrat.compute_ishrat (the ISHRAT scores the regression reads)",
                    "sspi_flask_app.api.core.sspi.ms.neq.ginipt.compute_ginipt (unwrapped view function, collection handles stubbed)",
                    "sspi_flask_app.api.core.sspi.ms.neq.ginipt.impute_ginipt (unwrapped view function, collection handles stubbed)",
                    f"sspi_flask_app.api.resources.utilities.regression_imputation with sklearn {sklearn.__version__} LinearRegression (observed through a recording subclass)",
                ],
                fixtures=[WB_FIXTURE, WID_FIXTURE],
            ),
            "indicator_code": "GINIPT",
            "formula": f"goalpost(WB_GINIPT, {lg:g}, {ug:g})",
            "goalposts": [lg, ug],
            "unit": observed[0]["Unit"],
            "impute_route_exists": True,
            "series_fill": {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"},
            "observed_scores": records(observed, imputation=True),
            "series_fill_scores": records(series_fill, imputation=True),
            "regression": {
                "feature_indicator": feature,
                "model_string": predicted[0]["ImputationRegessionModel"],
                "details": predicted[0]["ImputationDetails"],
                "training": [
                    {"country_code": country, "year": int(year), "feature_score": float(x), "target_score": float(y)}
                    for (country, year), x, y in zip(fit["X"].index, fit["X"][feature].tolist(), fit["y"].tolist())
                ],
                "coefficient": float(fit["model"].coef_[0]),
                "intercept": float(fit["model"].intercept_),
                "prediction_inputs": [
                    {"country_code": country, "year": int(year), "feature_score": float(x), "raw_prediction": float(p)}
                    for (country, year), x, p in zip(prediction_frame.index, prediction_frame[feature].tolist(), prediction_values.tolist())
                ],
                "recipients": sorted({d["CountryCode"] for d in predicted}),
                "predicted_scores": sorted(
                    (
                        {
                            "country_code": d["CountryCode"],
                            "year": d["Year"],
                            "score": d["Score"],
                            "unit": d["Unit"],
                            "inputs": [],
                            "imputed": d["Imputed"],
                            "imputation_method": d["ImputationMethod"],
                            "imputation_distance": d["ImputationDistance"],
                            "value": d["Value"],
                            "lower_goalpost": d["LowerGoalpost"],
                            "upper_goalpost": d["UpperGoalpost"],
                        }
                        for d in predicted
                    ),
                    key=lambda d: (d["country_code"], d["year"]),
                ),
            },
            "legacy_impute_error": None,
            "legacy_output_conflicts": {
                "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
                "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
            },
        },
    )
    years = [d["Year"] for d in observed]
    fill_years = [d["Year"] for d in series_fill]
    predicted_years = [d["Year"] for d in predicted]
    print(
        f"GINIPT: {len(observed)} observed ({min(years)}-{max(years)}), {len(series_fill)} series-fill ({min(fill_years)}-{max(fill_years)}), "
        f"{len(predicted)} predicted ({min(predicted_years)}-{max(predicted_years)}) for {sorted({d['CountryCode'] for d in predicted})}; "
        f"training n={len(fit['X'])}, coef={fit['model'].coef_[0]!r}, intercept={fit['model'].intercept_!r}"
    )
    print(f"from {commit}")


if __name__ == "__main__":
    main()
