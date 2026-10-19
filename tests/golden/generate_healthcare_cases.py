"""Generate the Healthcare golden files from the committed source fixtures:

    unsdg_cstunt_cases.json, wb_gdp_percap_curprice_usd_cases.json
    cstunt_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_healthcare_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed fixtures (one raw document per UN SDG
pivot row and per World Bank row, as the collectors stored them); the
``compute_cstunt`` and ``impute_cstunt`` view functions run unwrapped from
their decorators with their collection handles stubbed the same way, the
impute route reading the scores the compute route "stored" and the GDP rows
the World Bank cleaner produced. The legacy ``LinearRegression`` (sklearn)
is observed, not replaced: a recording subclass notes the training frame,
the fitted coefficient and intercept, and the prediction inputs.

Two inputs are run through the same legacy code: the verbatim sample of the
live 2.2.1 response (``2_2_1_sample.json``, where every country has every
year 2000-2024 and the series fill produces nothing) and a synthetic variant
with year values blanked (``2_2_1_synthetic_gaps.json``) that exercises the
series fill. Three failing situations are recorded with the legacy error:
no UNSDG_CSTUNT rows, no GDP rows, and no country without CSTUNT data.

Only CSTUNT is generated. ATBRTH, DPTCOV, PHYSPC and FAMPLN read WHO Global
Health Observatory datasets, a source with no ingestion path in the new
backend (see ``docs/indicator-migration.md``, Healthcare indicators not
ported).
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

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
UNSDG_FIXTURE = "tests/fixtures/unsdg/2_2_1_sample.json"
UNSDG_GAPS_FIXTURE = "tests/fixtures/unsdg/2_2_1_synthetic_gaps.json"
WB_FIXTURE = "tests/fixtures/wb/NY.GDP.PCAP.CD_sample.json"
CSTUNT_SERIES, CSTUNT_DIMENSIONS = "SH_STA_STNT", {"sex": "BOTHSEX", "age": "<5Y"}  # unsdg_cstunt.py
GDP = "WB_GDP_PERCAP_CURPRICE_USD"


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "pg", "hlc", indicator.lower(), "methodology.md")) as fh:
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
    import sklearn
    from pycountry import countries
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources import utilities

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixtures):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixtures": fixtures,
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

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

    # ------------------------------------------------------------------ UNSDG_CSTUNT
    unsdg_metadata = MetadataStub("UNSDG")

    def clean_unsdg(fixture_path):
        with open(os.path.join(NEW_REPO, fixture_path)) as fh:
            fixture = json.load(fh)
        module = importlib.import_module("sspi_flask_app.api.core.datasets.unsdg.unsdg_cstunt")
        module.sspi_raw_api_data = RawStub(fixture["data"])
        module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), unsdg_metadata
        cleaned = dataset_cleaner_registry["UNSDG_CSTUNT"]()
        assert cleaned and all(d["DatasetCode"] == "UNSDG_CSTUNT" for d in cleaned)
        selected = [r for r in fixture["data"] if r["series"] == CSTUNT_SERIES and all(r.get(k) == v for k, v in CSTUNT_DIMENSIONS.items())]
        skipped = sorted({(r["geoAreaCode"], r["geoAreaName"]) for r in selected if iso(r["geoAreaCode"]) is None})
        missing = sum(1 for r in selected if iso(r["geoAreaCode"]) for e in json.loads(r["years"]) if is_missing(e["value"]))
        return module, cleaned, skipped, missing

    cleaner_module, cstunt_clean, skipped, missing = clean_unsdg(UNSDG_FIXTURE)
    _, gaps_clean, gaps_skipped, gaps_missing = clean_unsdg(UNSDG_GAPS_FIXTURE)
    observations = observation_records(cstunt_clean)
    write(
        "unsdg_cstunt_cases.json",
        {
            "generated_from": generated_from([f"{cleaner_module.__name__}.clean_unsdg_cstunt (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.unsdg.extract_sdg, filter_sdg"], [UNSDG_FIXTURE]),
            "dataset_code": "UNSDG_CSTUNT",
            "series_code": CSTUNT_SERIES,
            "dimensions": CSTUNT_DIMENSIONS,
            "observations": observations,
            "skipped_areas": [list(s) for s in skipped],
            "empty_source_values": missing,
            "descriptions": sorted({d["Description"] for d in cstunt_clean}),
            "legacy_document_keys": sorted({k for d in cstunt_clean for k in d}),
        },
    )
    years = [o["year"] for o in observations]
    print(f"UNSDG_CSTUNT: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values; synthetic gaps: {len(gaps_clean)} observations")

    # ------------------------------------------------------------------ WB_GDP_PERCAP_CURPRICE_USD
    with open(os.path.join(NEW_REPO, WB_FIXTURE)) as fh:
        _, wb_rows = json.load(fh)
    wb_metadata = MetadataStub("WB")
    wb_module = importlib.import_module("sspi_flask_app.api.core.datasets.wb.wb_gdp_curprice_usd")
    wb_module.sspi_raw_api_data = RawStub(wb_rows)
    wb_module.sspi_clean_api_data, wb_module.sspi_metadata = CleanStub(), wb_metadata
    gdp_clean = dataset_cleaner_registry[GDP]()
    assert gdp_clean and all(d["DatasetCode"] == GDP for d in gdp_clean)
    gdp_skipped = sorted({(r["countryiso3code"] or r["country"]["id"], r["country"]["value"]) for r in wb_rows if not countries.get(alpha_3=r["countryiso3code"] or r["country"]["id"])})
    gdp_missing = sum(1 for r in wb_rows if countries.get(alpha_3=r["countryiso3code"] or r["country"]["id"]) and (r["value"] == "NaN" or not r["value"]))
    gdp_observations = observation_records(gdp_clean)
    write(
        "wb_gdp_percap_curprice_usd_cases.json",
        {
            "generated_from": generated_from([f"{wb_module.__name__}.clean_wb_gdp_percap_curprice_usd (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], [WB_FIXTURE]),
            "dataset_code": GDP,
            "series_code": "NY.GDP.PCAP.CD",
            "observations": gdp_observations,
            "skipped_areas": [list(s) for s in gdp_skipped],
            "empty_source_values": gdp_missing,
            "descriptions": sorted({d["Description"] for d in gdp_clean}),
            "legacy_document_keys": sorted({k for d in gdp_clean for k in d}),
        },
    )
    years = [o["year"] for o in gdp_observations]
    print(f"{GDP}: {len(gdp_observations)} observations, {len({o['country_code'] for o in gdp_observations})} countries, {min(years)}-{max(years)}, {len(gdp_skipped)} skipped areas, {gdp_missing} missing values")

    # ------------------------------------------------------------------ CSTUNT
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
    front = frontmatter("CSTUNT")
    lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]

    def run_routes(clean_rows, gdp_rows):
        """compute_cstunt then impute_cstunt on fresh stub collections; (observed, imputed, error)."""
        module = importlib.import_module("sspi_flask_app.api.core.sspi.pg.hlc.cstunt")
        clean = CollectionStub(list(clean_rows) + list(gdp_rows))
        indicator, imputed_collection = CollectionStub(), CollectionStub()
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = unsdg_metadata, clean
        module.sspi_indicator_data, module.sspi_imputed_data = indicator, imputed_collection
        observed = unwrap(module.compute_cstunt)()
        try:
            imputed = unwrap(module.impute_cstunt)()
            error = None
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            imputed, error = [], f"{type(exc).__name__}: {exc}"
        return observed, imputed, error

    def regression_record(fit, predicted):
        (feature,) = list(fit["X"].columns)
        prediction_frame, prediction_values = fit["predictions"][0]
        return {
            "feature_code": feature,
            "feature_goalposts": [0, 100000],
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
        }

    def case_for(clean_rows, label):
        fits.clear()
        observed, imputed, error = run_routes(clean_rows, gdp_clean)
        assert error is None, error
        series_fill = [d for d in imputed if "Datasets" in d]
        predicted = [d for d in imputed if "Datasets" not in d]
        assert len(fits) == 1 and len(fits[0]["predictions"]) == 1 and len(series_fill) + len(predicted) == len(imputed)
        fill_units = sorted({d["Unit"] for d in series_fill})
        record = {
            "observed_scores": records(observed, imputation=True),
            "series_fill_scores": records(series_fill, imputation=True),
            "series_fill_units": fill_units,
            "regression": regression_record(fits[0], predicted),
            "legacy_output_conflicts": output_conflicts(observed, imputed),
        }
        fit = fits[0]
        print(
            f"CSTUNT ({label}): {len(observed)} observed, {len(series_fill)} series-fill (units {fill_units}), {len(predicted)} predicted "
            f"({min(d['Year'] for d in predicted)}-{max(d['Year'] for d in predicted)}) for {len({d['CountryCode'] for d in predicted})} countries; "
            f"training n={len(record['regression']['training'])}, coef={fit['model'].coef_[0]!r}, intercept={fit['model'].intercept_!r}"
        )
        return observed, record

    observed, verbatim = case_for(cstunt_clean, "verbatim sample")
    _, gaps = case_for(gaps_clean, "synthetic gaps")
    gaps = {"observations": observation_records(gaps_clean), "skipped_areas": [list(s) for s in gaps_skipped], "empty_source_values": gaps_missing, **gaps}

    failures = {}
    for name, clean_rows, gdp_rows in (
        ("no_cstunt_rows", [], gdp_clean),
        ("no_gdp_rows", cstunt_clean, []),
        ("no_country_without_cstunt", cstunt_clean, [d for d in gdp_clean if d["CountryCode"] in {o["CountryCode"] for o in cstunt_clean}]),
    ):
        fits.clear()
        failed_observed, _, error = run_routes(clean_rows, gdp_rows)
        assert error is not None, name
        failures[name] = {"observed_scores": len(failed_observed), "legacy_impute_error": error}
        print(f"CSTUNT {name}: {len(failed_observed)} observed, impute route: {error}")

    write(
        "cstunt_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner functions for UNSDG_CSTUNT and WB_GDP_PERCAP_CURPRICE_USD (Mongo handles stubbed)",
                    "sspi_flask_app.api.core.sspi.pg.hlc.cstunt.compute_cstunt (unwrapped view function, collection handles stubbed)",
                    "sspi_flask_app.api.core.sspi.pg.hlc.cstunt.impute_cstunt (unwrapped view function, collection handles stubbed)",
                    f"sspi_flask_app.api.resources.utilities.regression_imputation with sklearn {sklearn.__version__} LinearRegression (observed through a recording subclass)",
                ],
                [UNSDG_FIXTURE, UNSDG_GAPS_FIXTURE, WB_FIXTURE],
            ),
            "indicator_code": "CSTUNT",
            "formula": f"goalpost(UNSDG_CSTUNT, {lg:g}, {ug:g})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [lg, ug],
            "unit": observed[0]["Unit"],
            "impute_route_exists": True,
            "series_fill": {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"},
            "verbatim": verbatim,
            "synthetic_gaps": gaps,
            "legacy_failures": failures,
            "legacy_impute_error": None,
        },
    )
    print(f"from {commit}")


if __name__ == "__main__":
    main()
