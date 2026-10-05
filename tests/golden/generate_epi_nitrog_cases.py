"""Generate tests/golden/epi_nitrog_cases.json and tests/golden/nitrog_cases.json
from the OLD implementation, on the committed 2024 EPI fixture.

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_epi_nitrog_cases.py

The fixture is ``P5_Indicator/SNM_ind_na.csv`` from ``epi2024indicators.zip``,
the archive the legacy collector downloaded (recovered from the Internet
Archive's capture of the legacy URL; the live URL now serves an HTML page).
The registered ``clean_epi_nitrog`` cleaner runs with its Mongo handles
stubbed to return that CSV text, exactly as ``parse_epi_csv`` saw it, then
``score_indicator`` applies the ``compute_nitrog`` lambda with the goalposts
the route reads from the legacy methodology file. NITROG has no impute route.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
FIXTURE = "tests/fixtures/epi/epi2024indicators_P5_Indicator_SNM_ind_na.csv"
GOALPOST_INPUTS = [-5.0, 0.0, 24.3, 50.5, 99.9, 100.0, 120.0]


def main() -> None:
    import importlib

    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources.utilities import goalpost, score_indicator

    from generate_legacy_cleaner_cases import CleanStub, MetadataStub

    class RawTextStub:
        def __init__(self, text):
            self.text = text

        def fetch_raw_data(self, source_info):
            return [{"Raw": self.text}]

    with open(os.path.join(OLD_REPO, "methodology", "sus", "lnd", "nitrog", "methodology.md")) as fh:
        frontmatter = yaml.safe_load(fh.read().split("---")[1])
    lg, ug = frontmatter["LowerGoalpost"], frontmatter["UpperGoalpost"]
    with open(os.path.join(NEW_REPO, FIXTURE), encoding="utf-8", newline="") as fh:
        csv_text = fh.read()

    module = importlib.import_module("sspi_flask_app.api.core.datasets.epi.epi_nitrog")
    module.sspi_raw_api_data = RawTextStub(csv_text)
    module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), MetadataStub()
    cleaned = dataset_cleaner_registry["EPI_NITROG"]()
    assert cleaned and all(d["DatasetCode"] == "EPI_NITROG" for d in cleaned)
    observations = sorted(
        ({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned),
        key=lambda d: (d["country_code"], d["year"]),
    )

    scored, incomplete = score_indicator(json.loads(json.dumps(cleaned)), "NITROG", score_function=lambda EPI_NITROG: goalpost(EPI_NITROG, lg, ug), unit="Index")
    scores = sorted(
        (
            {
                "country_code": d["CountryCode"],
                "year": d["Year"],
                "score": d["Score"],
                "unit": d["Unit"],
                "inputs": [{"dataset_code": x["DatasetCode"], "value": x["Value"], "unit": x["Unit"]} for x in d["Datasets"]],
            }
            for d in scored
        ),
        key=lambda d: (d["country_code"], d["year"]),
    )

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = csv_text.splitlines()
    header = next(iter(__import__("csv").reader([rows[0]])))
    cells = sum(len(next(iter(__import__("csv").reader([line])))) - 3 for line in rows[1:])

    dataset_payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": generated_at,
            "source_functions": ["sspi_flask_app.api.core.datasets.epi.epi_nitrog.clean_epi_nitrog (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.epi.parse_epi_csv"],
            "fixture": FIXTURE,
            "fixture_origin": "P5_Indicator/SNM_ind_na.csv inside https://epi.yale.edu/downloads/epi2024indicators.zip, Internet Archive capture 2026-04-24 (the live URL serves HTML)",
        },
        "dataset_code": "EPI_NITROG",
        "series_code": "SNM",
        "archive": "epi2024indicators",
        "year_columns": [c for c in header if c not in ("code", "iso", "country")],
        "value_cells": cells,
        "observations": observations,
        "skipped_areas": [],
        "legacy_document_keys": sorted({k for d in cleaned for k in d}),
    }
    with open(os.path.join(HERE, "epi_nitrog_cases.json"), "w") as fh:
        json.dump(dataset_payload, fh, indent=1, allow_nan=False)

    indicator_payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": generated_at,
            "source_functions": [
                "sspi_flask_app.api.core.datasets.epi.epi_nitrog.clean_epi_nitrog (registered @dataset_cleaner, Mongo handles stubbed)",
                "sspi_flask_app.api.resources.utilities.score_indicator",
                "sspi_flask_app.api.resources.utilities.goalpost",
            ],
            "route": "sspi_flask_app/api/core/sspi/sus/lnd/nitrog.py compute_nitrog",
            "fixture": FIXTURE,
        },
        "indicator_code": "NITROG",
        "goalposts": {"lower": lg, "upper": ug, "read_from": "methodology/sus/lnd/nitrog/methodology.md"},
        "impute_route_exists": False,
        "scores": scores,
        "incomplete_count": len(incomplete),
        "goalpost_cases": [{"value": v, "score": goalpost(v, lg, ug)} for v in GOALPOST_INPUTS],
    }
    with open(os.path.join(HERE, "nitrog_cases.json"), "w") as fh:
        json.dump(indicator_payload, fh, indent=1, allow_nan=False)
    years = [o["year"] for o in observations]
    print(f"EPI_NITROG: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {cells} value cells")
    print(f"NITROG: {len(scores)} scores, {len(incomplete)} incomplete, goalposts ({lg}, {ug}) from {commit}")


if __name__ == "__main__":
    main()
