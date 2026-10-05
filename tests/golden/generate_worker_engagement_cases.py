"""Generate the Worker Engagement golden files from the committed ILO fixtures:

    ilo_employ_to_pop_cases.json, employ_cases.json
    ilo_colbar_cases.json, colbar_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_worker_engagement_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed SDMX-JSON responses (so the legacy
``extract_ilo`` / ``parse_sdmx_json_to_tabular`` / ``filter_ilo`` path runs
unchanged); the ``compute_*`` and ``impute_*`` view functions run unwrapped
from their decorators with their collection handles stubbed the same way.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import CollectionStub, identities, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
CASES = (
    # indicator, dataset, fixture, legacy collector request
    ("EMPLOY", "ILO_EMPLOY_TO_POP", "tests/fixtures/ilo/DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json", {"dataflow": "DF_EMP_DWAP_SEX_AGE_RT", "key": ".A..SEX_T.AGE_YTHADULT_Y15-64", "url_params": ["startPeriod=2000"]}),
    ("COLBAR", "ILO_COLBAR", "tests/fixtures/ilo/DF_ILR_CBCT_NOC_RT.json", {"dataflow": "DF_ILR_CBCT_NOC_RT", "key": "", "url_params": ["startPeriod=1990-01-01", "endPeriod=2024-12-31"]}),
)


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "ms", "wen", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class RawTextStub:
    """``sspi_raw_api_data``: one raw document holding the response text, as the legacy collector stored it."""

    def __init__(self, text):
        self.text = text

    def fetch_raw_data(self, source_info):
        return [{"Raw": self.text}]


class MetadataStub:
    def get_source_info(self, code):
        return {"OrganizationCode": "ILO"}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def main() -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = MetadataStub()
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

    for indicator, dataset, fixture, request in CASES:
        with open(os.path.join(NEW_REPO, fixture), encoding="utf-8") as fh:
            text = fh.read()
        message = json.loads(text)
        structure = message["data"]["structures"][0]
        cleaner_module = importlib.import_module(f"sspi_flask_app.api.core.datasets.ilo.{dataset.lower()}")
        cleaner_module.sspi_raw_api_data = RawTextStub(text)
        cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        observations = observation_records(cleaned)
        null_values = sum(1 for data_set in message["data"]["dataSets"] for series in data_set["series"].values() for cells in series["observations"].values() if not cells or cells[0] is None)
        area_codes = [v["id"] for d in structure["dimensions"]["series"] if d["id"] == "REF_AREA" for v in d["values"]]
        write(
            f"{dataset.lower()}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"{cleaner_module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)",
                        "sspi_flask_app.api.datasource.ilo.extract_ilo, parse_sdmx_json_to_tabular, filter_ilo",
                    ],
                    fixture,
                ),
                "dataset_code": dataset,
                "source_request": request,
                "series_dimensions": {d["id"]: [v["id"] for v in d["values"]] for d in structure["dimensions"]["series"] if d["id"] != "REF_AREA"},
                "observations": observations,
                "skipped_areas": sorted(code for code in area_codes if any(ch.isdigit() for ch in code)),
                "empty_source_values": null_values,
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        years = [o["year"] for o in observations]
        print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} areas, {min(years)}-{max(years)}")

        clean_collection, indicator_data, imputed_data = CollectionStub(cleaned), CollectionStub(), CollectionStub()
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.ms.wen.{indicator.lower()}")
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
                "series_fill": {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"},
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
