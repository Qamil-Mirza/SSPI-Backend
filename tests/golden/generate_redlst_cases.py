"""Generate tests/golden/redlst_cases.json from the OLD implementation.

Run ONCE inside the old repository's virtualenv (its modules import a Mongo
client at import time, but nothing here touches the database):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_redlst_cases.py

The committed 15.5.1 fixture rows are cleaned by the legacy ``extract_sdg`` +
``filter_sdg`` exactly as ``clean_unsdg_redlst`` does, then scored by the
legacy ``score_indicator`` with the ``compute_redlst`` lambda. The goalposts
are the ones the route reads at runtime from the legacy methodology file.
Legacy REDLST has no impute route, so there is nothing else to record.

``goalpost_cases`` pushes handwritten values, including ones outside
[0, 1], through the legacy ``goalpost`` with the same goalposts.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from datetime import datetime, timezone

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
FIXTURE = "tests/fixtures/unsdg/15_5_1_sample.json"
GOALPOST_INPUTS = [-0.2, 0.0, 0.25, 0.40526, 0.5, 0.83317, 1.0, 1.3]


def main() -> None:
    from sspi_flask_app.api.datasource.unsdg import extract_sdg, filter_sdg
    from sspi_flask_app.api.resources.utilities import goalpost, score_indicator

    with open(os.path.join(OLD_REPO, "methodology", "sus", "eco", "redlst", "methodology.md")) as fh:
        frontmatter = yaml.safe_load(fh.read().split("---")[1])
    lg, ug = frontmatter["LowerGoalpost"], frontmatter["UpperGoalpost"]

    with open(os.path.join(NEW_REPO, FIXTURE)) as fh:
        fixture = json.load(fh)
    clean = filter_sdg(
        extract_sdg([{"Raw": copy.deepcopy(row)} for row in fixture["data"]]),
        {"ER_RSK_LST": "UNSDG_REDLST"},
        {"units": "Unit", "seriesDescription": "Description"},
        ["goal", "indicator", "series", "seriesCount", "target", "geoAreaCode", "geoAreaName"],
    )
    scored, incomplete = score_indicator(
        clean, "REDLST", score_function=lambda UNSDG_REDLST: goalpost(UNSDG_REDLST, lg, ug), unit="Index"
    )
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
    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "sspi_flask_app.api.datasource.unsdg.extract_sdg",
                "sspi_flask_app.api.datasource.unsdg.filter_sdg",
                "sspi_flask_app.api.resources.utilities.score_indicator",
                "sspi_flask_app.api.resources.utilities.goalpost",
            ],
            "route": "sspi_flask_app/api/core/sspi/sus/eco/redlst.py compute_redlst",
            "fixture": FIXTURE,
        },
        "indicator_code": "REDLST",
        "goalposts": {"lower": lg, "upper": ug, "read_from": "methodology/sus/eco/redlst/methodology.md"},
        "impute_route_exists": False,
        "historical_discrepancy": (
            "local/SSPIStaticData2018.csv: all 49 REDLST rows satisfy score = (raw - 0.5) / 0.5, implying goalposts "
            "(0.5, 1); the executable route, the methodology file and local/IndicatorDetailsStatic.csv all say (0, 1). "
            "Preserved, unresolved. This file records the executable (0, 1) behaviour."
        ),
        "scores": scores,
        "incomplete_count": len(incomplete),
        "goalpost_cases": [{"value": v, "score": goalpost(v, lg, ug)} for v in GOALPOST_INPUTS],
    }
    out = os.path.join(HERE, "redlst_cases.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"REDLST: wrote {len(scores)} scores, {len(incomplete)} incomplete, goalposts ({lg}, {ug}) from {commit}")


if __name__ == "__main__":
    main()
