"""Generate ``unsdg_<dataset>_cases.json`` by running the OLD dataset cleaner
function itself on a committed source fixture.

Run inside the old repository's virtualenv (the cleaner modules import the
Mongo-backed collections at import time; a reachable MongoDB is needed to
import them, not to run them):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_legacy_cleaner_cases.py \
        --dataset UNSDG_STKHLM --fixture tests/fixtures/unsdg/12_4_1_sample.json

Unlike ``generate_unsdg_cases.py``, which re-applies ``extract_sdg`` and
``filter_sdg`` with the cleaner's arguments, this script calls the registered
``@dataset_cleaner`` function with its three collection handles replaced by
in-memory stubs. Whatever the cleaner does beyond series selection, such as a
dimension filter or a derived series, is therefore the legacy code's own
output. The file format is the one ``test_golden_unsdg.py`` replays.
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


class RawStub:
    def __init__(self, rows):
        self.rows = rows

    def fetch_raw_data(self, source_info):
        return [{"Raw": copy.deepcopy(row)} for row in self.rows]


class CleanStub:
    def delete_many(self, query):
        return 0

    def insert_many(self, documents):
        return len(documents)


class MetadataStub:
    def get_source_info(self, code):
        return {"OrganizationCode": "UNSDG"}

    def record_dataset_range(self, documents, code):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--fixture", required=True, help="path relative to the new repo root")
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    args = parser.parse_args()
    out = os.path.join(HERE, f"{args.dataset.lower()}_cases.json")

    import importlib

    from pycountry import countries
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    module_name = f"sspi_flask_app.api.core.datasets.unsdg.{args.dataset.lower()}"
    module = importlib.import_module(module_name)
    with open(os.path.join(NEW_REPO, args.fixture)) as fh:
        fixture = json.load(fh)
    module.sspi_raw_api_data = RawStub(fixture["data"])
    module.sspi_clean_api_data = CleanStub()
    module.sspi_metadata = MetadataStub()

    cleaned = dataset_cleaner_registry[args.dataset]()
    assert cleaned and all(d["DatasetCode"] == args.dataset for d in cleaned), "cleaner returned nothing or foreign documents"
    observations = sorted(
        ({"country_code": d["CountryCode"], "year": d["Year"], "value": d["Value"], "unit": d["Unit"]} for d in cleaned),
        key=lambda d: (d["country_code"], d["year"]),
    )
    source_text = open(module.__file__).read()
    import re

    idcode = re.findall(r'"([A-Z0-9_]+)":\s*"' + re.escape(args.dataset) + '"', source_text)
    assert len(idcode) == 1, f"expected one idcode_map entry for {args.dataset}, found {idcode}"
    series_code = idcode[0]
    assert series_code, "could not determine the series the cleaner selects"
    dimension = re.search(r"filter_sdg\((?:[^()]|\([^()]*\))*?(\w+)=\"(\w+)\"", source_text, re.S)
    dimensions = {dimension.group(1): dimension.group(2)} if dimension else None

    def iso(code):
        c = countries.get(numeric=f"{int(code):03d}")
        return c.alpha_3 if c else None

    series_rows = [row for row in fixture["data"] if row["series"] == series_code and (dimensions is None or all(row.get(k) == v for k, v in dimensions.items()))]
    skipped = sorted({(row["geoAreaCode"], row["geoAreaName"]) for row in series_rows if iso(row["geoAreaCode"]) is None})

    commit = subprocess.check_output(["git", "-C", args.old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", args.old_repo, "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [f"{module_name}.{dataset_cleaner_registry[args.dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)"],
            "fixture": args.fixture,
        },
        "dataset_code": args.dataset,
        "series_code": series_code,
        "dimensions": dimensions,
        "observations": observations,
        "skipped_areas": [list(s) for s in skipped],
        "legacy_document_keys": sorted({k for d in cleaned for k in d}),
    }
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"{args.dataset}: wrote {len(observations)} observations, {len(skipped)} skipped areas, series {series_code}, dimensions {dimensions} to {os.path.relpath(out, NEW_REPO)} from {commit}")


if __name__ == "__main__":
    main()
