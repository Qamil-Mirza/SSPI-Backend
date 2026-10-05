"""Generate the Energy golden files from the committed UN SDG fixtures:

    nrgint_cases.json, airpol_cases.json

(the two dataset files, ``unsdg_nrgint_cases.json`` and
``unsdg_airpol_cases.json``, come from ``generate_legacy_cleaner_cases.py``).

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_legacy_cleaner_cases.py \
        --dataset UNSDG_NRGINT --fixture tests/fixtures/unsdg/7_3_1_sample.json
    env/bin/python /path/to/sspi-backend/tests/golden/generate_legacy_cleaner_cases.py \
        --dataset UNSDG_AIRPOL --fixture tests/fixtures/unsdg/11_6_2_sample.json
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_energy_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed pivot rows in source order; the
``compute_*`` and ``impute_*`` view functions run unwrapped from their
decorators with their collection handles stubbed the same way, so the
indicator collection returns documents in insertion order, as MongoDB does.

ALTNRG has its own generator, ``generate_iea_cases.py``.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import CollectionStub, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub
from generate_fao_land_cases import conflicts, records

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
CASES = (
    # indicator, dataset, fixture, what the impute route does to the scores
    ("NRGINT", "UNSDG_NRGINT", "tests/fixtures/unsdg/7_3_1_sample.json", {"forward_to": 2023, "backward_to": None, "reference_class": None}),
    ("AIRPOL", "UNSDG_AIRPOL", "tests/fixtures/unsdg/11_6_2_sample.json", {"forward_to": 2023, "backward_to": 2000, "reference_class": {"recipient_group": "SSPI67", "recipients": "members with no observed score", "years": [2000, 2023]}}),
)


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "sus", "nrg", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"OrganizationCode": "UNSDG"}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def main() -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        metadata = MetadataStub(json.load(fh))
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    for indicator, dataset, fixture, extrapolation in CASES:
        with open(os.path.join(NEW_REPO, fixture), encoding="utf-8") as fh:
            rows = json.load(fh)["data"]
        cleaner_module = importlib.import_module(f"sspi_flask_app.api.core.datasets.unsdg.{dataset.lower()}")
        cleaner_module.sspi_raw_api_data, cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = RawStub(rows), CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset

        indicator_data, imputed_data = CollectionStub(), CollectionStub()
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.sus.nrg.{indicator.lower()}")
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = metadata, CollectionStub(cleaned)
        module.sspi_indicator_data, module.sspi_imputed_data = indicator_data, imputed_data
        observed = unwrap(getattr(module, f"compute_{indicator.lower()}"))()
        imputed = unwrap(getattr(module, f"impute_{indicator.lower()}"))()
        front = frontmatter(indicator)
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (unit,) = {d["Unit"] for d in observed + imputed}
        scored_countries = {d["CountryCode"] for d in observed}
        payload = {
            "generated_from": {
                "repository": "sspi-data-webapp",
                "commit": commit,
                "working_tree_dirty": dirty,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_functions": [
                    f"registered @dataset_cleaner function for {dataset} (Mongo handles stubbed)",
                    f"{module.__name__}.compute_{indicator.lower()} (unwrapped view function, collection handles stubbed)",
                    f"{module.__name__}.impute_{indicator.lower()} (unwrapped view function, collection handles stubbed)",
                ],
                "fixture": fixture,
            },
            "indicator_code": indicator,
            "formula": f"goalpost({dataset}, {lg:g}, {ug:g})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [lg, ug],
            "unit": unit,
            "impute_route_exists": True,
            "score_extrapolation": extrapolation,
            "reference_class_recipients": sorted(c for c in metadata.country_group("SSPI67") if c not in scored_countries) if extrapolation["reference_class"] else [],
            "observed_scores": records(observed),
            "imputed_scores": records(imputed),
            "legacy_impute_error": None,
            "legacy_output_conflicts": conflicts(observed, imputed),
        }
        with open(os.path.join(HERE, f"{indicator.lower()}_cases.json"), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)
        methods = {}
        for d in imputed:
            methods[d["ImputationMethod"]] = methods.get(d["ImputationMethod"], 0) + 1
        print(f"{indicator}: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}), {len(imputed)} imputed {methods}, unit {unit!r}, conflicts {payload['legacy_output_conflicts']}")
    print(f"from {commit}")


if __name__ == "__main__":
    main()
