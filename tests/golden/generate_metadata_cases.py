"""Generate tests/golden/metadata_cases.json from the OLD metadata loader.

Run ONCE inside the old repository's virtualenv (the old loader needs a Flask
app context and imports a Mongo client at module import):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_metadata_cases.py

It calls the old file-walking loader functions directly, so the fixture
reflects the methodology/ and datasets/ files at HEAD rather than whatever a
Mongo instance happens to hold. Only semantic values are recorded, and the
documented migration edits from PROVENANCE.yaml are applied, so the fixture
holds the values the new catalog is expected to produce.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROVENANCE = os.path.join(NEW_REPO, "src", "sspi", "metadata", "data", "PROVENANCE.yaml")


def apply_edit(record: dict, field: str, new):
    *parents, leaf = field.split(".")
    target = record
    for key in parents:
        target = target[key]
    target[leaf] = new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    parser.add_argument("--out", default=os.path.join(HERE, "metadata_cases.json"))
    args = parser.parse_args()
    old_repo = args.old_repo
    sys.path.insert(0, old_repo)

    from flask import Flask
    from sspi_flask_app.models.database import sspi_metadata

    app = Flask("golden", instance_path=os.path.join(old_repo, "instance"))
    with app.app_context():
        item_details = sspi_metadata.load_methodology_files()
        dataset_details = sspi_metadata.load_dataset_files()

    with open(PROVENANCE) as fh:
        provenance = yaml.safe_load(fh)

    indicators = {}
    for detail in item_details:
        if detail.get("ItemType") != "Indicator":
            continue
        parts = detail["TreePath"].split("/")  # sspi/<pillar>/<category>/<indicator>
        indicators[detail["ItemCode"]] = {
            "code": detail["ItemCode"],
            "name": detail["ItemName"],
            "pillar_code": parts[1].upper(),
            "category_code": parts[2].upper(),
            "dataset_codes": list(detail["DatasetCodes"]),
            "lower_goalpost": None if detail.get("LowerGoalpost") is None else float(detail["LowerGoalpost"]),
            "upper_goalpost": None if detail.get("UpperGoalpost") is None else float(detail["UpperGoalpost"]),
        }

    referenced = {code for ind in indicators.values() for code in ind["dataset_codes"]}
    datasets = {}
    for detail in dataset_details:
        code = detail["DatasetCode"]
        if code not in referenced:
            continue
        source = detail["Source"]
        datasets[code] = {
            "code": code,
            "name": detail["DatasetName"],
            "dataset_type": detail["DatasetType"],
            "unit": detail.get("Unit"),
            "source": {
                "organization_code": source.get("OrganizationCode"),
                "query_code": source.get("QueryCode"),
                "organization_series_code": source.get("OrganizationSeriesCode"),
            },
        }

    for edit in provenance["edits"]:
        kind, filename = edit["file"].split("/")
        code = filename.removesuffix(".yaml")
        apply_edit(indicators[code] if kind == "indicators" else datasets[code], edit["field"], edit["new"])

    unresolved = [
        {"code": u["code"], "referenced_by": list(u["referenced_by"])}
        for u in provenance["unresolved_datasets"]
    ]
    for u in unresolved:
        assert u["code"] not in datasets, u

    commit = subprocess.check_output(["git", "-C", old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", old_repo, "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "sspi_flask_app.models.database.sspi_metadata.load_methodology_files",
                "sspi_flask_app.models.database.sspi_metadata.load_dataset_files",
            ],
            "edits_applied_from": "src/sspi/metadata/data/PROVENANCE.yaml",
        },
        "indicators": [indicators[c] for c in sorted(indicators)],
        "datasets": [datasets[c] for c in sorted(datasets)],
        "unresolved_datasets": unresolved,
    }
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"wrote {len(indicators)} indicators, {len(datasets)} datasets, {len(unresolved)} unresolved from {commit}")


if __name__ == "__main__":
    main()
