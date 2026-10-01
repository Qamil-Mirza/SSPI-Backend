"""Generate ``<indicator>_cases.json`` for an indicator whose legacy compute
route is "clean rows in, ``score_indicator`` with a formula out".

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_compute_route_cases.py --indicator CHMPOL

The dependency datasets are cleaned by the registered legacy
``@dataset_cleaner`` functions (Mongo handles stubbed, see
``generate_legacy_cleaner_cases.py``) from the committed fixtures, then scored
by the legacy ``score_indicator`` with the compute route's own formula, copied
verbatim below with the legacy ``goalpost``. Any year filter the route applies
is applied here too. Only the compute route is recorded; impute routes, where
they exist, are separate evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# indicator -> (route file, {dataset: fixture}, formula factory taking legacy goalpost)
ROUTES = {
    "CHMPOL": {
        "route": "sspi_flask_app/api/core/sspi/sus/lnd/chmpol.py compute_chmpol",
        "fixtures": {code: "tests/fixtures/unsdg/12_4_1_sample.json" for code in ("UNSDG_STKHLM", "UNSDG_MINMAT", "UNSDG_MONTRL", "UNSDG_BASELA", "UNSDG_ROTDAM")},
        "formula_text": "(UNSDG_STKHLM + UNSDG_MINMAT + UNSDG_MONTRL + UNSDG_BASELA + UNSDG_ROTDAM) / 5 / 100",
        "goalposts": None,
        "impute_route_exists": False,
    },
    "WATMAN": {
        "route": "sspi_flask_app/api/core/sspi/sus/lnd/watman.py compute_watman",
        "fixtures": {"UNSDG_CWUEFF": "tests/fixtures/unsdg/6_4_1_sample.json", "UNSDG_WTSTRS": "tests/fixtures/unsdg/6_4_2_sample.json"},
        "formula_text": "(goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2",
        "goalposts": {"UNSDG_CWUEFF": [-20, 50], "UNSDG_WTSTRS": [100, 0]},
        "impute_route_exists": True,
    },
}


def formula(indicator: str, goalpost):
    if indicator == "CHMPOL":

        def score_chmpol(UNSDG_STKHLM, UNSDG_MINMAT, UNSDG_MONTRL, UNSDG_BASELA, UNSDG_ROTDAM):
            return (UNSDG_STKHLM + UNSDG_MINMAT + UNSDG_MONTRL + UNSDG_BASELA + UNSDG_ROTDAM) / 5 / 100

        return score_chmpol
    if indicator == "WATMAN":

        def score_watman(UNSDG_CWUEFF, UNSDG_WTSTRS) -> float:
            return (goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2

        return score_watman
    raise SystemExit(f"no formula for {indicator}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indicator", required=True, choices=sorted(ROUTES))
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp")))
    args = parser.parse_args()
    spec = ROUTES[args.indicator]

    import importlib

    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.resources.utilities import goalpost, score_indicator

    from generate_legacy_cleaner_cases import CleanStub, MetadataStub, RawStub

    clean: list[dict] = []
    for dataset, fixture in spec["fixtures"].items():
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.unsdg.{dataset.lower()}")
        with open(os.path.join(NEW_REPO, fixture)) as fh:
            module.sspi_raw_api_data = RawStub(json.load(fh)["data"])
        module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), MetadataStub()
        clean.extend(dataset_cleaner_registry[dataset]())

    scored, incomplete = score_indicator(clean, args.indicator, score_function=formula(args.indicator, goalpost), unit="Index")
    scores = sorted(
        (
            {
                "country_code": d["CountryCode"],
                "year": d["Year"],
                "score": d["Score"],
                "unit": d["Unit"],
                "inputs": sorted(({"dataset_code": x["DatasetCode"], "value": x["Value"], "unit": x["Unit"]} for x in d["Datasets"]), key=lambda x: x["dataset_code"]),
            }
            for d in scored
        ),
        key=lambda d: (d["country_code"], d["year"]),
    )
    incomplete_identities = sorted({(d["CountryCode"], d["Year"]) for d in incomplete})

    commit = subprocess.check_output(["git", "-C", args.old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", args.old_repo, "status", "--porcelain"], text=True).strip())
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "registered @dataset_cleaner functions for each dependency (Mongo handles stubbed)",
                "sspi_flask_app.api.resources.utilities.score_indicator",
                "sspi_flask_app.api.resources.utilities.goalpost",
            ],
            "route": spec["route"],
            "fixtures": sorted(set(spec["fixtures"].values())),
        },
        "indicator_code": args.indicator,
        "formula": spec["formula_text"],
        "goalposts": spec["goalposts"],
        "impute_route_exists": spec["impute_route_exists"],
        "scores": scores,
        "incomplete_identities": [list(i) for i in incomplete_identities],
    }
    out = os.path.join(HERE, f"{args.indicator.lower()}_cases.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"{args.indicator}: wrote {len(scores)} scores, {len(incomplete_identities)} incomplete identities to {os.path.relpath(out, NEW_REPO)} from {commit}")


if __name__ == "__main__":
    main()
