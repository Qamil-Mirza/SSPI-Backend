"""Generate the FAO Land Use golden files from the committed bulk-file sample:

    unfao_frstlv_cases.json, unfao_frstav_cases.json   (DEFRST datasets)
    unfao_crbnlv_cases.json, unfao_crbnav_cases.json   (CARBON datasets)
    defrst_cases.json, carbon_cases.json               (both legacy routes each)

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_fao_land_cases.py

The legacy collector read the FAOSTAT JSON API with ``area_cs=ISO3``; that
endpoint now requires authentication, so the committed fixture is a sample of
the official normalized bulk file instead. The legacy cleaner cannot read the
bulk layout, so :func:`as_legacy_api_rows` presents each bulk row the way the
API did: the ISO3 code where the area's M49 code is a country (the same
pycountry mapping the new adapter uses) and the FAO area code otherwise, which
the legacy filter drops because it contains digits, exactly as it dropped the
API's non-ISO3 aggregate codes. Values are passed as the strings the bulk file
holds; the legacy cleaner converts them with ``float``. Everything after that
adaptation is the legacy module's own code: the four registered cleaners (with
their Mongo handles stubbed), ``score_indicator`` with the routes' formulas and
the year filter the compute routes apply, and the ``impute_defrst`` /
``impute_carbon`` view functions unwrapped from their decorators.

The impute routes are recorded as they behave, including any identity that
appears both in the compute output and in the impute output, or twice in the
impute output (``legacy_output_conflicts``). The new backend cannot store
two rows for one identity, so such a variant is a registered divergence, not
parity evidence; see docs/indicator-migration.md.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
FIXTURE = "tests/fixtures/fao/Inputs_LandUse_E_All_Data_(Normalized)_sample.csv"
# dataset -> (element code, item code) as the legacy collectors requested them (CARBON: legacy API element 7215 is the bulk file's 72151)
SERIES = {
    "UNFAO_FRSTLV": ("5110", "6717"),
    "UNFAO_FRSTAV": ("5110", "6717"),
    "UNFAO_CRBNLV": ("72151", "6646"),
    "UNFAO_CRBNAV": ("72151", "6646"),
}
INDICATORS = {"DEFRST": ("UNFAO_FRSTLV", "UNFAO_FRSTAV"), "CARBON": ("UNFAO_CRBNLV", "UNFAO_CRBNAV")}


def as_legacy_api_rows(rows, element, item):
    from pycountry import countries

    out = []
    for row in rows:
        if row["Element Code"] != element or row["Item Code"] != item:
            continue
        m49 = row["Area Code (M49)"].lstrip("'")
        country = countries.get(numeric=f"{int(m49):03d}")
        out.append(
            {
                "Area Code (ISO3)": country.alpha_3 if country is not None else row["Area Code"],
                "Area": row["Area"],
                "Year": row["Year"],
                "Value": row["Value"],
                "Unit": row["Unit"],
                "Flag": row["Flag"],
            }
        )
    return out


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


def score_record(d):
    return {
        "country_code": d["CountryCode"],
        "year": d["Year"],
        "score": d["Score"],
        "unit": d["Unit"],
        "inputs": sorted((slim(x) for x in d.get("Datasets", [])), key=lambda x: x["dataset_code"]),
        "imputed": bool(d.get("Imputed", False)),
        "imputation_method": d.get("ImputationMethod"),
        "imputation_distance": d.get("ImputationDistance"),
    }


def records(scored):
    return sorted((score_record(d) for d in scored), key=lambda d: (d["country_code"], d["year"]))


def identities(docs):
    return [list(i) for i in sorted({(d["CountryCode"], d["Year"]) for d in docs})]


def conflicts(observed, imputed):
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    return {
        "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
        "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
    }


def goalposts(code):
    text = open(os.path.join(OLD_REPO, "methodology", "sus", "lnd", code.lower(), "methodology.md")).read()
    return (float(re.search(r"^LowerGoalpost: (.+)$", text, re.M).group(1)), float(re.search(r"^UpperGoalpost: (.+)$", text, re.M).group(1)))


def main() -> None:
    import importlib

    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.api.resources.utilities import goalpost

    from generate_legacy_cleaner_cases import CleanStub, RawStub
    from generate_watman_cases import FindStub

    class MetadataStub:
        def get_source_info(self, code):
            return {"OrganizationCode": "UNFAO"}

        def record_dataset_range(self, documents, code):
            return None

        def get_goalposts(self, code):
            return goalposts(code)

    with open(os.path.join(NEW_REPO, FIXTURE), encoding="utf-8", newline="") as fh:
        bulk_rows = list(csv.DictReader(fh))

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())

    def generated_from(functions):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixture": FIXTURE,
            "fixture_adaptation": "bulk rows presented as FAOSTAT API objects by generate_fao_land_cases.as_legacy_api_rows (M49 -> ISO3 via pycountry, FAO area code otherwise)",
        }

    clean = {}
    for dataset, (element, item) in SERIES.items():
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.unfao.{dataset.lower()}")
        module.sspi_raw_api_data = RawStub([{"data": as_legacy_api_rows(bulk_rows, element, item)}])
        module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), MetadataStub()
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        clean[dataset] = cleaned
        observations = sorted(
            ({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned),
            key=lambda d: (d["country_code"], d["year"]),
        )
        api_rows = as_legacy_api_rows(bulk_rows, element, item)
        skipped = sorted({(r["Area Code (ISO3)"], r["Area"]) for r in api_rows if len(r["Area Code (ISO3)"]) != 3 or any(ch.isdigit() for ch in r["Area Code (ISO3)"])})
        payload = {
            "generated_from": generated_from([f"{module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)"]),
            "dataset_code": dataset,
            "source_filters": {"domain": "RL", "element_code": element, "item_code": item},
            "observations": observations,
            "skipped_areas": [list(s) for s in skipped],
            "empty_source_values": sum(1 for r in api_rows if r["Value"] == ""),
            "legacy_document_keys": sorted({k for d in cleaned for k in d}),
        }
        with open(os.path.join(HERE, f"{dataset.lower()}_cases.json"), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)
        years = [o["year"] for o in observations]
        print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas")

    def make_score_defrst(lg, ug):
        def score_defrst(UNFAO_FRSTLV, UNFAO_FRSTAV) -> float:  # compute_defrst.score_defrst, verbatim
            if UNFAO_FRSTAV == 0:
                return 0
            return goalpost((UNFAO_FRSTLV - UNFAO_FRSTAV) / UNFAO_FRSTAV * 100, lg, ug)

        return score_defrst

    def make_score_carbon(lg, ug):
        def score_carbon(UNFAO_CRBNLV, UNFAO_CRBNAV) -> float:  # compute_carbon.score_carbon, verbatim
            if UNFAO_CRBNAV == 0:
                return 0
            return goalpost((UNFAO_CRBNLV - UNFAO_CRBNAV) / UNFAO_CRBNAV * 100, lg, ug)

        return score_carbon

    def run_variant(indicator, level, average, name, note, mutate):
        """Both legacy routes on the fixture after ``mutate`` (identity for the committed fixture)."""
        lg, ug = goalposts(indicator)
        score = {"DEFRST": make_score_defrst, "CARBON": make_score_carbon}[indicator](lg, ug)
        variant_clean = {}
        for code in (level, average):
            module = importlib.import_module(f"sspi_flask_app.api.core.datasets.unfao.{code.lower()}")
            module.sspi_raw_api_data = RawStub([{"data": mutate(as_legacy_api_rows(bulk_rows, *SERIES[code]))}])
            module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), MetadataStub()
            variant_clean[code] = dataset_cleaner_registry[code]()
        combined = variant_clean[level] + variant_clean[average]
        filtered = [o for o in combined if (o["DatasetCode"] == level and o.get("Year", 0) >= 2000) or o["DatasetCode"] == average]  # the compute routes' filter
        observed, incomplete = utilities.score_indicator(json.loads(json.dumps(filtered)), indicator, score_function=score, unit="Index")

        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.sus.lnd.{indicator.lower()}")
        route = getattr(module, f"impute_{indicator.lower()}")
        while hasattr(route, "__wrapped__"):
            route = route.__wrapped__
        module.sspi_metadata = MetadataStub()
        module.sspi_imputed_data = FindStub({})
        module.sspi_indicator_data = FindStub({json.dumps({"IndicatorCode": indicator}, sort_keys=True): observed})
        module.sspi_clean_api_data = FindStub({json.dumps({"DatasetCode": code}, sort_keys=True): variant_clean[code] for code in (level, average)})
        imputed = route()
        return {
            "name": name,
            "note": note,
            "level_countries": sorted({d["CountryCode"] for d in variant_clean[level]}),
            "scores": records(observed),
            "incomplete_identities": identities(incomplete),
            "legacy_impute_error": None,
            "imputed_scores": records(imputed),
            "legacy_output_conflicts": conflicts(observed, imputed),
        }

    def as_committed(rows):
        return rows

    def without(country):
        def mutate(rows):
            return [r for r in rows if r["Area Code (ISO3)"] != country]

        return mutate

    RECIPIENT_WITH_DATA = {"DEFRST": "ARE", "CARBON": "KWT"}
    for indicator, (level, average) in INDICATORS.items():
        lg, ug = goalposts(indicator)
        recipient = RECIPIENT_WITH_DATA[indicator]
        variants = [
            run_variant(indicator, level, average, "fixture_as_committed", f"The committed bulk-file sample as it is: {recipient} has source rows, so the unconditional reference-class rule of the legacy impute route produces imputed scores for country-years the compute route also scores.", as_committed),
            run_variant(
                indicator,
                level,
                average,
                f"without_{recipient.lower()}_source_rows",
                f"{recipient}'s {level} rows removed before cleaning, the source state the legacy route's hard-coded recipient list was written against: no identity is both observed and imputed.",
                without(recipient),
            ),
        ]
        payload = {
            "generated_from": generated_from(
                [
                    f"registered @dataset_cleaner functions for {level}, {average} (Mongo handles stubbed)",
                    f"sspi_flask_app.api.resources.utilities.score_indicator with compute_{indicator.lower()}'s score function and year filter",
                    f"{module.__name__}.impute_{indicator.lower()} (unwrapped view function, collection handles stubbed)",
                ]
            ),
            "indicator_code": indicator,
            "formula": f"0 if {average} == 0 else goalpost(({level} - {average}) / {average} * 100, {lg:g}, {ug:g})",
            "goalposts": [lg, ug],
            "level_year_filter": ">= 2000",
            "impute_route_exists": True,
            "reference_class_recipients": {"DEFRST": ["BEL", "ARE", "LUX"], "CARBON": ["KWT", "BEL", "LUX"]}[indicator],
            "variants": variants,
        }
        with open(os.path.join(HERE, f"{indicator.lower()}_cases.json"), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)
        for v in variants:
            c = v["legacy_output_conflicts"]
            print(f"{indicator} {v['name']}: {len(v['scores'])} observed, {len(v['incomplete_identities'])} incomplete, {len(v['imputed_scores'])} imputed; "
                  f"conflicts observed&imputed={len(c['observed_and_imputed'])}, duplicate imputed={len(c['duplicate_imputed'])}")
    print(f"from {commit}")


if __name__ == "__main__":
    main()
