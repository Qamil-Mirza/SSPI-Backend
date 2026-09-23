"""Generate semantic golden cases for a UNSDG dataset from the OLD cleaner.

Run ONCE per dataset inside the old repository's virtualenv (the old datasource
module imports the Mongo-backed models at import time, so a reachable MongoDB
is needed to *import* it, not to run the pure functions):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_unsdg_cases.py \
        --dataset UNSDG_MARINE --series ER_MRN_MPA --fixture tests/fixtures/unsdg/14_5_1_sample.json
    env/bin/python .../generate_unsdg_cases.py --dataset UNSDG_TERRST --series ER_PTD_TERR --fixture tests/fixtures/unsdg/15_1_2_sample.json
    env/bin/python .../generate_unsdg_cases.py --dataset UNSDG_FRSHWT --series ER_PTD_FRHWTR --fixture tests/fixtures/unsdg/15_1_2_sample.json

The legacy ``extract_sdg`` + ``filter_sdg`` pair is applied exactly as the
legacy ``unsdg_<dataset>.py`` cleaners do (series map, rename map, drop list),
and only semantic values are recorded: (country_code, year, value, unit) and
the areas that produced nothing. The committed JSON files are self-contained.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--series", required=True)
    parser.add_argument("--fixture", required=True, help="path relative to the new repo root")
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    args = parser.parse_args()
    out = os.path.join(HERE, f"{args.dataset.lower()}_cases.json")

    from pycountry import countries
    from sspi_flask_app.api.datasource.unsdg import extract_sdg, filter_sdg

    with open(os.path.join(NEW_REPO, args.fixture)) as fh:
        fixture = json.load(fh)
    raw_docs = [{"Raw": copy.deepcopy(row)} for row in fixture["data"]]

    cleaned = filter_sdg(
        extract_sdg(raw_docs),
        {args.series: args.dataset},
        {"units": "Unit", "seriesDescription": "Description"},
        ["goal", "indicator", "series", "seriesCount", "target", "geoAreaCode", "geoAreaName"],
    )
    observations = sorted(
        ({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned),
        key=lambda d: (d["country_code"], d["year"]),
    )

    def iso(code):
        c = countries.get(numeric=f"{int(code):03d}")
        return c.alpha_3 if c else None

    series_rows = [row for row in fixture["data"] if row["series"] == args.series]
    skipped = sorted((row["geoAreaCode"], row["geoAreaName"]) for row in series_rows if iso(row["geoAreaCode"]) is None)
    produced = {d["CountryCode"] for d in cleaned}
    assert all(iso(row["geoAreaCode"]) in produced for row in series_rows if iso(row["geoAreaCode"])), "legacy dropped a mapped area"

    commit = subprocess.check_output(["git", "-C", args.old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", args.old_repo, "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "sspi_flask_app.api.datasource.unsdg.extract_sdg",
                "sspi_flask_app.api.datasource.unsdg.filter_sdg",
            ],
            "fixture": args.fixture,
        },
        "dataset_code": args.dataset,
        "series_code": args.series,
        "observations": observations,
        "skipped_areas": skipped,
        "legacy_document_keys": sorted({k for d in cleaned for k in d}),
    }
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"{args.dataset}: wrote {len(observations)} observations, {len(skipped)} skipped areas to {os.path.relpath(out, NEW_REPO)} from {commit}")


if __name__ == "__main__":
    main()
