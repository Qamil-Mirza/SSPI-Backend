"""Generate the ALTNRG golden files from the committed IEA fixture:

    iea_tlcoal_cases.json, iea_natgas_cases.json, iea_nclear_cases.json,
    iea_hydrop_cases.json, iea_geopwr_cases.json, iea_biowas_cases.json,
    iea_fsloil_cases.json, altnrg_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_iea_cases.py

Everything recorded is the legacy code's own output. The seven registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed ``TESbySource`` rows, one raw document
per row as the legacy collector stored them (so ``clean_iea_data_altnrg``
and ``filter_iea_data`` run unchanged). ``compute_altnrg`` and
``impute_altnrg`` run unwrapped from their decorators with their collection
handles stubbed the same way; the impute route's own ``score_indicator``
call is observed to record the country-years it left incomplete, which the
route computes and discards.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import types
from datetime import datetime, timezone

from generate_fao_land_cases import conflicts, slim
from generate_inequality_cases import observation_records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
FIXTURE = "tests/fixtures/iea/TESbySource_sample.json"
INDICATOR = "TESbySource"
DATASETS = ("IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL")


def frontmatter():
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "sus", "nrg", "altnrg", "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"OrganizationCode": "IEA", "QueryCode": INDICATOR}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        front = frontmatter()
        return front["LowerGoalpost"], front["UpperGoalpost"]


class AllDocuments:
    """A collection whose every query matches every document it holds (the routes only ask for the seven datasets)."""

    def __init__(self, documents=()):
        self.documents = list(documents)

    def find(self, query):
        return json.loads(json.dumps(self.documents))  # fresh copies, as Mongo would return

    def delete_many(self, query):
        self.documents = []

    def insert_many(self, documents):
        self.documents.extend(json.loads(json.dumps(documents)))


def score_record(d):
    datasets = d.get("Datasets", [])
    return {
        "country_code": d["CountryCode"],
        "year": d["Year"],
        "score": d["Score"],
        "unit": d["Unit"],
        "inputs": sorted((slim(x) for x in datasets if not x.get("Computed")), key=lambda x: x["dataset_code"]),
        "computed": [{"dataset_code": x["DatasetCode"], "value": x["Value"], "unit": x["Unit"]} for x in datasets if x.get("Computed")],
        "imputed": bool(d.get("Imputed", False)),
        "imputation_method": d.get("ImputationMethod"),
        "imputation_distance": d.get("ImputationDistance"),
    }


def records(scored):
    return sorted((score_record(d) for d in scored), key=lambda d: (d["country_code"], d["year"]))


def incomplete_records(documents):
    return sorted(
        ({"country_code": d["CountryCode"], "year": d["Year"], "datasets": sorted(x["DatasetCode"] for x in d["Datasets"])} for d in documents),
        key=lambda d: (d["country_code"], d["year"]),
    )


def main() -> None:
    import pycountry
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        metadata = MetadataStub(json.load(fh))
    with open(os.path.join(NEW_REPO, FIXTURE), encoding="utf-8") as fh:
        rows = json.load(fh)

    def generated_from(functions):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixture": FIXTURE,
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    clean = []
    for dataset in DATASETS:
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.iea.{dataset.lower()}")
        module.sspi_raw_api_data, module.sspi_clean_api_data, module.sspi_metadata = RawStub(rows), CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        with open(module.__file__) as fh:
            product = re.search(r'filter_iea_data\(raw_data, "' + dataset + r'", "(\w+)"\)', fh.read()).group(1)  # the product the cleaner selects
        selected = [r for r in rows if r["product"] == product]
        mapped = [r for r in selected if pycountry.countries.get(alpha_3=r["country"])]
        write(
            f"{dataset.lower()}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"{module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)",
                        "sspi_flask_app.api.datasource.iea.clean_iea_data_altnrg, filter_iea_data",
                    ]
                ),
                "dataset_code": dataset,
                "source_request": {"url": f"https://api.iea.org/stats/indicator/{INDICATOR}", "indicator": INDICATOR},
                "dimensions": {"product": product},
                "product_label": sorted({r["productLabel"] for r in selected}),
                "observations": observation_records(cleaned),
                "skipped_areas": sorted({r["country"] for r in selected} - {r["country"] for r in mapped}),
                "empty_source_values": sum(1 for r in mapped if r["value"] is None),
                "zero_source_values": sum(1 for r in mapped if r["value"] is not None and not r["value"]),
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        years = [d["Year"] for d in cleaned]
        print(f"{dataset} ({product}): {len(cleaned)} observations, {len({d['CountryCode'] for d in cleaned})} countries, {min(years)}-{max(years)}")
        clean.extend(cleaned)

    module = importlib.import_module("sspi_flask_app.api.core.sspi.sus.nrg.altnrg")
    module.app = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))
    module.parse_json = lambda value: value
    module.sspi_metadata, module.sspi_clean_api_data = metadata, AllDocuments(clean)
    module.sspi_indicator_data, module.sspi_incomplete_indicator_data, module.sspi_imputed_data = AllDocuments(), AllDocuments(), AllDocuments()
    observed = unwrap(module.compute_altnrg)()
    observed_incomplete = module.sspi_incomplete_indicator_data.find({})
    legacy_score_indicator, left_incomplete = module.score_indicator, []

    def recording_score_indicator(*args, **kwargs):
        complete, incomplete = legacy_score_indicator(*args, **kwargs)
        left_incomplete.extend(json.loads(json.dumps(incomplete)))
        return complete, incomplete

    module.score_indicator = recording_score_indicator
    imputed = unwrap(module.impute_altnrg)()
    module.score_indicator = legacy_score_indicator
    front = frontmatter()
    (unit,) = {d["Unit"] for d in observed + imputed}
    write(
        "altnrg_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner functions for the seven IEA datasets (Mongo handles stubbed)",
                    f"{module.__name__}.compute_altnrg (unwrapped view function, collection handles stubbed)",
                    f"{module.__name__}.impute_altnrg (unwrapped view function, collection handles stubbed)",
                ]
            ),
            "indicator_code": "ALTNRG",
            "dataset_codes": list(DATASETS),
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
            "unit": unit,
            "computed_series": {"dataset_code": "IEA_ALTNRG_PERCENTAGE", "on_observed_scores": True, "on_imputed_scores": any(x.get("Computed") for d in imputed for x in d["Datasets"])},
            "impute_route_exists": True,
            "imputation": {"zero_fill": {"recipient_group": "SSPI67", "recipients": "members with no row in the dataset", "years": [2000, 2023], "unit": "PJ"}, "backward_to": 2000, "forward_to": 2023, "interpolation": "every interior gap, any year"},
            "observed_scores": records(observed),
            "observed_incomplete": incomplete_records(observed_incomplete),
            "imputed_scores": records(imputed),
            "incomplete_after_imputation": incomplete_records(left_incomplete),
            "legacy_impute_error": None,
            "legacy_output_conflicts": conflicts(observed, imputed),
        },
    )
    print(f"ALTNRG: {len(observed)} observed, {len(observed_incomplete)} incomplete; {len(imputed)} imputed, {len(left_incomplete)} incomplete after imputation; unit {unit!r}")
    print(f"from {commit}")


if __name__ == "__main__":
    main()
