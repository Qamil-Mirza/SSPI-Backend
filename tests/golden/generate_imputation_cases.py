"""Generate the imputation golden fixtures from the OLD implementation.

Run ONCE inside the old repository's virtualenv (its utilities module imports
a Mongo client at import time, but nothing here touches the database):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_imputation_cases.py

Writes two files next to this script:

``imputation_cases.json``
    Handcrafted series and reference lists pushed through the legacy helpers
    ``extrapolate_backward``, ``extrapolate_forward``, ``interpolate_linear``
    and ``impute_reference_class_average`` in the exact order the BIODIV
    route chains them. Records every field of every added document.

``biodiv_imputation_cases.json``
    The committed UN fixture rows cleaned by the legacy ``extract_sdg`` +
    ``filter_sdg``, then pushed through the legacy ``impute_biodiv`` chain
    (minus Mongo) with a declared SSPI67 subset as recipients, scored with the
    impute route's own formula and filtered by ``filter_imputations``. Two
    variants: the fixture as committed, and one with Malaysia's marine series
    thinned so extrapolation and interpolation appear inside BIODIV.

Nothing is edited or corrected. Austria's marine values are the executable
legacy result, which conflicts with the retired 2018 static metadata (see the
``methodology_conflict`` note written into the file).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURES = os.path.join(NEW_REPO, "tests", "fixtures", "unsdg")

SERIES_ID = ["CountryCode", "DatasetCode"]
RECIPIENTS = ["AUT", "CHE", "KEN", "MYS", "USA"]  # SSPI67 members; CHE appears in no fixture series
THINNED_MYS_MARINE_YEARS = [2000, 2001, 2002, 2010, 2011, 2015, 2022, 2023, 2024, 2025]


def doc(country, year, value, dataset="DS_A", unit="PERCENT", **extra):
    d = {"DatasetCode": dataset, "CountryCode": country, "Year": year, "Value": value, "Unit": unit}
    d.update(extra)
    return d


SERIES_CASES = {
    "interior_gap": [doc("MYS", 2000, 10.0, Description="d"), doc("MYS", 2002, 20.0, Description="d")],
    "multi_year_gap": [doc("MYS", 2000, 10.0), doc("MYS", 2005, 20.0)],
    "before_first": [doc("MYS", 2003, 7.5), doc("MYS", 2004, 8.0)],
    "after_last": [doc("MYS", 2019, 1.0), doc("MYS", 2020, 2.0)],
    "single_observation": [doc("MYS", 2010, 42.0, SDGSeriesCode="X")],
    "starts_before_2000": [doc("MYS", 1995, 0.0), doc("MYS", 2005, 10.0)],
    "ends_after_2023": [doc("MYS", 2020, 4.0), doc("MYS", 2025, 9.0)],
    "two_countries": [doc("MYS", 2001, 1.0), doc("MYS", 2004, 4.0), doc("USA", 2022, 50.0), doc("USA", 2020, 40.0)],
    "two_datasets": [doc("MYS", 2001, 1.0, dataset="DS_A"), doc("MYS", 2003, 3.0, dataset="DS_B")],
    "unsorted_input_with_fractional_slope": [doc("MYS", 2003, 13.25, Description="hi"), doc("MYS", 2000, 10.5, Description="lo")],
    "complete_series": [doc("MYS", y, float(y)) for y in range(2000, 2024)],
}

REFERENCE_CASES = {
    "two_countries_three_years": {
        "reference": [doc("USA", 2000, 10.0), doc("USA", 2001, 20.0), doc("KEN", 2025, 60.0)],
        "target": "AUT",
        "start": 2000,
        "end": 2002,
    },
    "single_reference_row": {"reference": [doc("USA", 2010, 5.0)], "target": "AUT", "start": 2023, "end": 2023},
    "target_country_rows_would_count_too": {
        "reference": [doc("AUT", 2000, 100.0), doc("USA", 2000, 0.0)],
        "target": "AUT",
        "start": 2000,
        "end": 2000,
    },
}

REFERENCE_ERROR_CASES = {
    "empty_reference": {"reference": [], "target": "AUT", "start": 2000, "end": 2023},
    "mixed_units": {"reference": [doc("USA", 2000, 1.0, unit="PERCENT"), doc("KEN", 2000, 1.0, unit="KM2")], "target": "AUT", "start": 2000, "end": 2023},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    args = parser.parse_args()
    old_repo = args.old_repo
    sys.path.insert(0, old_repo)

    from sspi_flask_app.api.datasource.unsdg import extract_sdg, filter_sdg
    from sspi_flask_app.api.resources.utilities import (
        extrapolate_backward,
        extrapolate_forward,
        filter_imputations,
        goalpost,
        impute_reference_class_average,
        interpolate_linear,
        score_indicator,
    )

    commit = subprocess.check_output(["git", "-C", old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", old_repo, "status", "--porcelain"], text=True).strip())
    generated_from = {
        "repository": "sspi-data-webapp",
        "commit": commit,
        "working_tree_dirty": dirty,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_functions": [
            "sspi_flask_app.api.resources.utilities.impute_reference_class_average",
            "sspi_flask_app.api.resources.utilities.extrapolate_backward",
            "sspi_flask_app.api.resources.utilities.extrapolate_forward",
            "sspi_flask_app.api.resources.utilities.interpolate_linear",
            "sspi_flask_app.api.resources.utilities.score_indicator",
            "sspi_flask_app.api.resources.utilities.filter_imputations",
            "sspi_flask_app.api.core.sspi.sus.eco.biodiv.impute_biodiv (chain reproduced without Mongo)",
            "sspi_flask_app.api.core.sspi.sus.eco.biodiv.compute_biodiv (chain reproduced without Mongo)",
        ],
    }

    # --- series helper cases, chained exactly like the BIODIV route ---------------
    def chain(docs, start=2000, end=2023):
        backward = extrapolate_backward(docs, start, series_id=SERIES_ID, impute_only=True)
        after_backward = extrapolate_backward(docs, start, series_id=SERIES_ID)
        forward = extrapolate_forward(after_backward, end, series_id=SERIES_ID, impute_only=True)
        after_forward = extrapolate_forward(after_backward, end, series_id=SERIES_ID)
        interpolated = interpolate_linear(after_forward, series_id=SERIES_ID, impute_only=True)
        combined = interpolate_linear(after_forward, series_id=SERIES_ID)
        return {"backward": backward, "forward": forward, "interpolated": interpolated, "combined": combined}

    series_cases = []
    for name, docs in SERIES_CASES.items():
        original = deepcopy(docs)
        result = chain(docs)
        assert docs == original, f"{name}: legacy helper mutated its input"
        series_cases.append({"name": name, "start_year": 2000, "end_year": 2023, "input": original, **result})

    reference_cases = []
    for name, spec in REFERENCE_CASES.items():
        out = impute_reference_class_average(spec["target"], spec["start"], spec["end"], "Dataset", "DS_A", spec["reference"])
        reference_cases.append({"name": name, **spec, "output": out})
    reference_errors = []
    for name, spec in REFERENCE_ERROR_CASES.items():
        try:
            impute_reference_class_average(spec["target"], spec["start"], spec["end"], "Dataset", "DS_A", spec["reference"])
        except ValueError as exc:
            reference_errors.append({"name": name, **spec, "error": str(exc)})
        else:
            raise AssertionError(f"{name}: legacy did not raise")

    with open(os.path.join(HERE, "imputation_cases.json"), "w") as fh:
        json.dump(
            {"generated_from": generated_from, "series_cases": series_cases, "reference_cases": reference_cases, "reference_errors": reference_errors},
            fh,
            indent=1,
            allow_nan=False,
        )

    # --- BIODIV chain on the committed UN fixtures ------------------------------------
    def clean(fixture, series, code):
        with open(os.path.join(FIXTURES, fixture)) as fh:
            rows = json.load(fh)["data"]
        extracted = extract_sdg([{"Raw": r} for r in rows])
        return filter_sdg(
            extracted,
            {series: code},
            {"units": "Unit", "seriesDescription": "Description"},
            ["goal", "indicator", "series", "seriesCount", "target", "geoAreaCode", "geoAreaName"],
        )

    def impute_like_route(clean_docs, code, recipients):
        # Mirrors impute_biodiv: reference class from the untouched clean list, then
        # backward -> forward -> interpolate, each on the previous combined list.
        missing = sorted(set(recipients) - set(d.get("CountryCode", "") for d in clean_docs))
        reference = []
        for country in missing:
            reference.extend(impute_reference_class_average(country, 2000, 2023, "Dataset", code, clean_docs))
        combined = extrapolate_backward(clean_docs, 2000, series_id=SERIES_ID)
        combined = extrapolate_forward(combined, 2023, series_id=SERIES_ID)
        combined = interpolate_linear(combined, series_id=SERIES_ID)
        additions = [d for d in combined if d.get("Imputed")]
        return combined, reference, missing, additions

    def score_biodiv(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        return (UNSDG_MARINE + UNSDG_TERRST + UNSDG_FRSHWT) / 3 / 100  # impute route formula, verbatim

    def score_biodiv_compute(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):  # compute route formula, verbatim
        frshwt = goalpost(UNSDG_FRSHWT, 0, 100)
        terrst = goalpost(UNSDG_TERRST, 0, 100)
        marine = goalpost(UNSDG_MARINE, 0, 100)
        return (frshwt + terrst + marine) / 3

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

    def run_variant(name, marine, terrst, frshwt, note):
        datasets = {"UNSDG_MARINE": marine, "UNSDG_TERRST": terrst, "UNSDG_FRSHWT": frshwt}
        per_dataset = {}
        scoring_input = []
        all_reference = []
        for code in ["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"]:  # route order
            combined, reference, missing, additions = impute_like_route(datasets[code], code, RECIPIENTS)
            per_dataset[code] = {
                "clean_count": len(datasets[code]),
                "reference_observation_count": len(datasets[code]),
                "reference_mean": (sum(d["Value"] for d in datasets[code]) / len(datasets[code])) if datasets[code] else None,
                "recipients_missing": missing,
                "reference_rows": [slim(d) for d in reference],
                "series_additions": [slim(d) for d in additions],
            }
            scoring_input.extend(combined)
            all_reference.extend(reference)
        scored, incomplete = score_indicator(scoring_input + all_reference, "BIODIV", score_function=score_biodiv, unit="Index")
        imputed = filter_imputations(scored)
        imputed.sort(key=lambda d: (d["CountryCode"], d["Year"]))
        # The compute route: clean rows only, no year filter, mean of goalposts.
        observed, observed_incomplete = score_indicator(
            deepcopy(marine) + deepcopy(terrst) + deepcopy(frshwt), "BIODIV", score_function=score_biodiv_compute, unit="Index"
        )
        observed.sort(key=lambda d: (d["CountryCode"], d["Year"]))
        return {
            "name": name,
            "note": note,
            "recipients": RECIPIENTS,
            "start_year": 2000,
            "end_year": 2023,
            "datasets": per_dataset,
            "scored_count": len(scored),
            "incomplete_identities": sorted({(d["CountryCode"], d["Year"]) for d in incomplete}),
            "imputed_scores": [
                {
                    "country_code": d["CountryCode"],
                    "year": d["Year"],
                    "score": d["Score"],
                    "unit": d["Unit"],
                    "inputs": sorted((slim(x) for x in d["Datasets"]), key=lambda x: x["dataset_code"]),
                }
                for d in imputed
            ],
            "observed_only_scores_not_stored_by_impute_route": sorted(
                {(d["CountryCode"], d["Year"]) for d in scored if not any(x.get("Imputed") for x in d["Datasets"])}
            ),
            "observed_scores": [
                {
                    "country_code": d["CountryCode"],
                    "year": d["Year"],
                    "score": d["Score"],
                    "unit": d["Unit"],
                    "inputs": sorted((slim(x) for x in d["Datasets"]), key=lambda x: x["dataset_code"]),
                }
                for d in observed
            ],
            "observed_incomplete_identities": sorted({(d["CountryCode"], d["Year"]) for d in observed_incomplete}),
        }

    marine = clean("14_5_1_sample.json", "ER_MRN_MPA", "UNSDG_MARINE")
    terrst = clean("15_1_2_sample.json", "ER_PTD_TERR", "UNSDG_TERRST")
    frshwt = clean("15_1_2_sample.json", "ER_PTD_FRHWTR", "UNSDG_FRSHWT")
    thinned_marine = [d for d in marine if not (d["CountryCode"] == "MYS" and d["Year"] in THINNED_MYS_MARINE_YEARS)]

    variants = [
        run_variant("fixture_as_committed", marine, terrst, frshwt, "Every fixture country has complete 2000-2025 series; only reference-class imputation fires."),
        run_variant(
            "thinned_mys_marine",
            thinned_marine,
            terrst,
            frshwt,
            f"Malaysia marine years {THINNED_MYS_MARINE_YEARS} removed to exercise backward, interior and forward filling inside BIODIV.",
        ),
    ]
    payload = {
        "generated_from": {**generated_from, "fixtures": ["tests/fixtures/unsdg/14_5_1_sample.json", "tests/fixtures/unsdg/15_1_2_sample.json"]},
        "score_function": "(UNSDG_MARINE + UNSDG_TERRST + UNSDG_FRSHWT) / 3 / 100  # impute route; compute route uses mean of goalposts",
        "observed_score_function": "(goalpost(UNSDG_FRSHWT,0,100) + goalpost(UNSDG_TERRST,0,100) + goalpost(UNSDG_MARINE,0,100)) / 3  # compute route",
        "methodology_conflict": (
            "Austria (AUT) has no marine series at the UN source. The executable legacy impute route fills UNSDG_MARINE with the "
            "mean of every clean marine observation (all countries, all years incl. 2024-2025) and scores all three components. "
            "The retired 2018 static metadata (local/IndicatorDetailsStatic.csv) says landlocked countries omit marine and average two. "
            "The current methodology frontmatter says average three and has no imputation section. This fixture records the executable "
            "behaviour; the methodology decision is deferred."
        ),
        "variants": variants,
    }
    with open(os.path.join(HERE, "biodiv_imputation_cases.json"), "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(
        f"wrote {len(series_cases)} series cases, {len(reference_cases)} reference cases, {len(reference_errors)} reference errors, "
        f"{len(variants)} BIODIV variants ({[len(v['imputed_scores']) for v in variants]} imputed, "
        f"{[len(v['observed_scores']) for v in variants]} observed scores) from {commit}"
    )


if __name__ == "__main__":
    main()
