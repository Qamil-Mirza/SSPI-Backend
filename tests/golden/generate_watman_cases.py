"""Generate tests/golden/watman_cases.json: BOTH legacy WATMAN routes, run from
the committed 6.4.1 and 6.4.2 fixtures.

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_watman_cases.py

Compute route: the three legacy cleaners (Mongo handles stubbed, see
``generate_legacy_cleaner_cases.py``) then ``score_indicator`` with the
route's formula, exactly as ``compute_watman`` does.

Impute route: the legacy ``impute_watman`` view function itself, unwrapped
from its Flask/auth decorators, with its four collection handles replaced by
in-memory stubs fed from the compute route's output and the cleaned WUSEFF
rows, and ``score_indicator`` wrapped so the groups still incomplete after
imputation are recorded as well. Nothing is re-implemented here: the twelve
synthetic-CWUEFF recipients, the SGP reference class, the extrapolation
bounds and the ``filter_imputations`` rule are the legacy module's own code.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURES = {"UNSDG_CWUEFF": "tests/fixtures/unsdg/6_4_1_sample.json", "UNSDG_WUSEFF": "tests/fixtures/unsdg/6_4_1_sample.json", "UNSDG_WTSTRS": "tests/fixtures/unsdg/6_4_2_sample.json"}


class FindStub:
    def __init__(self, documents_by_query):
        self.documents_by_query = documents_by_query

    def find(self, query):
        key = json.dumps(query, sort_keys=True)
        return [json.loads(json.dumps(d)) for d in self.documents_by_query[key]]  # fresh copies, as Mongo would return

    def delete_many(self, query):
        return 0

    def insert_many(self, documents):
        return len(documents)


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


def records(scored):
    return sorted(
        (
            {"country_code": d["CountryCode"], "year": d["Year"], "score": d["Score"], "unit": d["Unit"], "inputs": sorted((slim(x) for x in d["Datasets"]), key=lambda x: x["dataset_code"])}
            for d in scored
        ),
        key=lambda d: (d["country_code"], d["year"]),
    )


def main() -> None:
    import importlib

    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.api.resources.utilities import goalpost

    from generate_legacy_cleaner_cases import CleanStub, MetadataStub, RawStub

    def run_variant(name, note, mutate):
        clean = {}
        for dataset, fixture in FIXTURES.items():
            module = importlib.import_module(f"sspi_flask_app.api.core.datasets.unsdg.{dataset.lower()}")
            with open(os.path.join(NEW_REPO, fixture)) as fh:
                rows = mutate(json.load(fh)["data"], fixture)
            module.sspi_raw_api_data = RawStub(rows)
            module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), MetadataStub()
            clean[dataset] = dataset_cleaner_registry[dataset]()

        def score_watman(UNSDG_CWUEFF, UNSDG_WTSTRS) -> float:  # compute_watman.score_watman, verbatim
            return (goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2

        observed, incomplete = utilities.score_indicator(clean["UNSDG_CWUEFF"] + clean["UNSDG_WTSTRS"], "WATMAN", score_function=score_watman, unit="Index")

        watman = importlib.import_module("sspi_flask_app.api.core.sspi.sus.lnd.watman")
        impute_route = watman.impute_watman
        while hasattr(impute_route, "__wrapped__"):
            impute_route = impute_route.__wrapped__
        watman.sspi_indicator_data = FindStub({json.dumps({"IndicatorCode": "WATMAN"}, sort_keys=True): observed})
        watman.sspi_incomplete_indicator_data = FindStub({json.dumps({"IndicatorCode": "WATMAN"}, sort_keys=True): incomplete})
        watman.sspi_clean_api_data = FindStub({json.dumps({"DatasetCode": "UNSDG_WUSEFF"}, sort_keys=True): clean["UNSDG_WUSEFF"]})
        watman.sspi_imputed_data = FindStub({})
        calls = []
        real_score_indicator = utilities.score_indicator

        def recording(*args, **kwargs):
            result = real_score_indicator(*args, **kwargs)
            calls.append(result)
            return result

        watman.score_indicator = recording
        variant = {
            "name": name,
            "note": note,
            "cwueff_countries": sorted({d["CountryCode"] for d in clean["UNSDG_CWUEFF"]}),
            "scores": records(observed),
            "incomplete_identities": [list(i) for i in sorted({(d["CountryCode"], d["Year"]) for d in incomplete})],
        }
        try:
            imputed = impute_route()
        except Exception as exc:  # the legacy route itself fails on this data; record that as the legacy behaviour
            variant["legacy_impute_error"] = f"{type(exc).__name__}: {exc}"
            variant["imputed_scores"] = None
            variant["imputed_incomplete_identities"] = None
        else:
            assert len(calls) == 1, "impute_watman is expected to call score_indicator once"
            variant["legacy_impute_error"] = None
            variant["imputed_scores"] = records(imputed)
            variant["imputed_incomplete_identities"] = [list(i) for i in sorted({(d["CountryCode"], d["Year"]) for d in calls[0][1]})]
        finally:
            watman.score_indicator = real_score_indicator
        return variant

    def as_committed(rows, fixture):
        return rows

    def sgp_without_2005(rows, fixture):
        if not fixture.endswith("6_4_1_sample.json"):
            return rows
        out = []
        for row in rows:
            row = dict(row)
            if row["geoAreaCode"] == "702" and row.get("activity") == "TOTAL":
                row["years"] = json.dumps([{"year": e["year"], "value": ""} if e["year"] == "[2005]" else e for e in json.loads(row["years"])])
            out.append(row)
        return out

    variants = [
        run_variant(
            "fixture_as_committed",
            "Singapore now reports water-use efficiency from 2005, so the derived CWUEFF exists for SGP and the route's unconditional SGP "
            "reference-class series duplicates it; the legacy impute route raises on current source data (WATMAN-3).",
            as_committed,
        ),
        run_variant(
            "sgp_without_2005",
            "Singapore's single baseline-period value (2005, TOTAL activity) blanked, which is the source state the route was written against: "
            "SGP has WUSEFF rows but no CWUEFF, receives the reference-class series, and CHE (listed) receives the synthetic series.",
            sgp_without_2005,
        ),
    ]

    commit = subprocess.check_output(["git", "-C", os.path.join(NEW_REPO, "..", "sspi-data-webapp"), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", os.path.join(NEW_REPO, "..", "sspi-data-webapp"), "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "registered @dataset_cleaner functions for UNSDG_CWUEFF, UNSDG_WTSTRS, UNSDG_WUSEFF (Mongo handles stubbed)",
                "sspi_flask_app.api.resources.utilities.score_indicator with compute_watman.score_watman",
                "sspi_flask_app.api.core.sspi.sus.lnd.watman.impute_watman (unwrapped view function, collection handles stubbed)",
            ],
            "fixtures": sorted(set(FIXTURES.values())),
        },
        "indicator_code": "WATMAN",
        "formula": "(goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2",
        "goalposts": {"UNSDG_CWUEFF": [-20, 50], "UNSDG_WTSTRS": [100, 0]},
        "impute_route_exists": True,
        "synthetic_cwueff_recipients": ["AUS", "BGD", "CAN", "CHE", "CHL", "DEU", "ISL", "LVA", "PER", "PHL", "SVN", "THA"],
        "reference_class_recipients": ["SGP"],
        "variants": variants,
    }
    out = os.path.join(HERE, "watman_cases.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    for v in variants:
        print(f"WATMAN {v['name']}: {len(v['scores'])} observed, {len(v['incomplete_identities'])} incomplete; impute: "
              + (v["legacy_impute_error"] or f"{len(v['imputed_scores'])} imputed, {len(v['imputed_incomplete_identities'])} incomplete after"))
    print(f"from {commit}")


if __name__ == "__main__":
    main()
