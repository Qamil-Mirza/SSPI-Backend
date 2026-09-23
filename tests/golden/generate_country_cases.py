"""Generate tests/golden/country_cases.json from the OLD country-group builders.

Run ONCE inside the old repository's virtualenv (the old module imports a
Mongo client at import time, but the builder methods used here never touch
the database):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_country_cases.py

It feeds ``local/country-groups.json`` to the same three builder methods the
legacy ``SSPIMetadata.load()`` uses, so the fixture holds exactly what the
legacy Mongo ``CountryGroup``, ``CountryGroupMap`` and ``CountryDetail``
documents contained: group order, member order, per-country group order and
pycountry names. Nothing is sorted or edited.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    parser.add_argument("--out", default=os.path.join(HERE, "country_cases.json"))
    args = parser.parse_args()
    old_repo = args.old_repo
    sys.path.insert(0, old_repo)

    import pycountry
    from sspi_flask_app.models.database import sspi_metadata

    with open(os.path.join(old_repo, "local", "country-groups.json")) as fh:
        country_groups = json.load(fh)

    group_docs = sspi_metadata.build_country_groups(country_groups)
    group_map = sspi_metadata.build_country_group_map(group_docs)["Metadata"]
    detail_docs = sspi_metadata.build_country_details(country_groups)

    groups = [
        {"code": d["Metadata"]["CountryGroupName"], "members": list(d["Metadata"]["Countries"])}
        for d in group_docs
        if d["DocumentType"] == "CountryGroup"
    ]
    group_names = next(d["Metadata"] for d in group_docs if d["DocumentType"] == "CountryGroups")
    countries = [
        {
            "code": d["Metadata"]["CountryCode"],
            "name": d["Metadata"]["Country"],
            "groups": list(d["Metadata"]["CountryGroups"]),
        }
        for d in detail_docs
    ]
    assert [g["code"] for g in groups] == group_names
    assert {c["code"] for c in countries} == set(group_map), "legacy dropped a code pycountry does not know"
    assert all(c["groups"] == group_map[c["code"]] for c in countries)

    commit = subprocess.check_output(["git", "-C", old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", old_repo, "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_file": "local/country-groups.json",
            "source_functions": [
                "sspi_flask_app.models.database.sspi_metadata.build_country_groups",
                "sspi_flask_app.models.database.sspi_metadata.build_country_group_map",
                "sspi_flask_app.models.database.sspi_metadata.build_country_details",
            ],
            "pycountry_version": getattr(pycountry, "__version__", None),
        },
        "groups": groups,
        "countries": countries,
    }
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False, ensure_ascii=False)
    print(f"wrote {len(groups)} groups, {len(countries)} countries from {commit}")


if __name__ == "__main__":
    main()
