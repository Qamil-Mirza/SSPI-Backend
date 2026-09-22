"""Generate tests/golden/scoring_cases.json from the OLD implementation.

Run this ONCE inside the old repository's virtualenv (it needs the old package
and a reachable MongoDB, because the old utilities module opens a Mongo client
at import time):

    cd ../sspi-data-webapp
    env/bin/python /path/to/sspi-backend/tests/golden/generate_scoring_cases.py

The committed JSON is self-contained; the normal test suite never needs the old
repository, MongoDB, or the old virtualenv.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from functions import make_functions  # noqa: E402


def obs(dataset_code, country_code, year, value, unit="Index", **extra):
    doc = {
        "DatasetCode": dataset_code,
        "CountryCode": country_code,
        "Year": year,
        "Value": value,
        "Unit": unit,
    }
    doc.update(extra)
    return doc


def build_cases() -> list[dict]:
    cases: list[dict] = []

    # 1. BIODIV: three UNSDG datasets, one extra dataset carried but unused,
    #    one group missing a dataset.
    biodiv = [
        obs("UNSDG_TERRST", "AUS", 2018, 50), obs("UNSDG_FRSHWT", "AUS", 2018, 50),
        obs("UNSDG_MARINE", "AUS", 2018, 50), obs("LDAREA", "AUS", 2018, 7692024, "km^2"),
        obs("UNSDG_TERRST", "URY", 2017, 61.2), obs("UNSDG_FRSHWT", "URY", 2017, 12.75),
        obs("UNSDG_MARINE", "URY", 2017, 100), obs("UNSDG_TERRST", "URY", 2018, 70),
        obs("UNSDG_FRSHWT", "URY", 2018, 80),  # URY 2018 lacks MARINE -> incomplete
        obs("UNSDG_TERRST", "MYS", 2018, 0), obs("UNSDG_FRSHWT", "MYS", 2018, 120.5),
        obs("UNSDG_MARINE", "MYS", 2018, -3),
    ]
    cases.append({
        "name": "biodiv_basic",
        "indicator_code": "BIODIV",
        "score_function": "biodiv_mean_goalpost",
        "unit": "Index",
        "computed_series": [],
        "observations": biodiv,
    })

    # 2. ALTNRG-style computed series feeding the score.
    iea_codes = ["IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL"]
    rng = random.Random(1)
    altnrg = []
    for country in ["USA", "MYS", "NOR"]:
        for year in (2010, 2011, 2012):
            for code in iea_codes:
                altnrg.append(obs(code, country, year, round(rng.uniform(0, 5000), 3), "PJ"))
    cases.append({
        "name": "altnrg_computed_series",
        "indicator_code": "ALTNRG",
        "score_function": "altnrg_score",
        "unit": "Index",
        "computed_series": [["IEA_ALTNRG_PERCENTAGE", "% of Total Energy Supply", "altnrg_percent"]],
        "observations": altnrg,
    })

    # 3. FORAID-style branching score and callable unit.
    foraid = []
    rng = random.Random(2)
    for country, donor in [("USA", True), ("KEN", False), ("MYS", False), ("NOR", True)]:
        for year in (2015, 2016):
            totdon = rng.uniform(0, 30) if donor else rng.uniform(0, 0.5)
            totrec = rng.uniform(0, 0.5) if donor else rng.uniform(0, 30)
            foraid += [
                obs("TOTDON", country, year, round(totdon, 4), "Billion USD"),
                obs("TOTREC", country, year, round(totrec, 4), "Billion USD"),
                obs("POPULN", country, year, rng.randint(3_000_000, 330_000_000), "People"),
                obs("GDPMKT", country, year, rng.randint(50_000_000_000, 20_000_000_000_000), "USD"),
            ]
    cases.append({
        "name": "foraid_branching_unit",
        "indicator_code": "FORAID",
        "score_function": "foraid_score",
        "unit": {"function": "foraid_unit"},
        "computed_series": [],
        "observations": foraid,
    })

    # 4. Inverted goalposts (lower > upper).
    cases.append({
        "name": "inverted_goalposts",
        "indicator_code": "MSWGEN",
        "score_function": "inverted_goalpost",
        "unit": "Index",
        "computed_series": [],
        "observations": [
            obs("EPI_MSWGEN", c, 2020, v, "kg/capita", Description="Municipal solid waste")
            for c, v in [("USA", 120), ("MYS", 45.5), ("NOR", 0), ("KEN", 100), ("DEU", 99.999)]
        ],
    })

    # 5. Random panel with gaps: three datasets, 20% of rows dropped.
    rng = random.Random(0)
    panel = []
    for country in ["USA", "MYS", "KEN", "NOR"]:
        for year in range(2010, 2016):
            for code in ("DS_A", "DS_B", "DS_C"):
                if rng.random() < 0.2:
                    continue
                panel.append(obs(code, country, year, round(rng.uniform(-10, 120), 6)))
    cases.append({
        "name": "random_panel_with_gaps",
        "indicator_code": "RANDOM",
        "score_function": "mean_of_three_goalposts",
        "unit": "Index",
        "computed_series": [],
        "observations": panel,
    })

    # 6. Chained computed series: second spec consumes the first.
    cases.append({
        "name": "chained_computed_series",
        "indicator_code": "CHAINS",
        "score_function": "uses_chained_computed",
        "unit": "Index",
        "computed_series": [["COMPUTED_TWICE", "x2", "twice"], ["COMPUTED_PLUS_ONE", "x2+1", "plus_one"]],
        "observations": [obs("BASE_X", c, y, v) for c, y, v in [("USA", 2000, 1.5), ("USA", 2001, 0.25), ("MYS", 2000, 4)]],
    })

    # 7. Value function raising for some groups (DENOM == 0) -> no series -> incomplete.
    cases.append({
        "name": "computed_series_exception_swallowed",
        "indicator_code": "RATIOS",
        "score_function": "uses_ratio",
        "unit": "Index",
        "computed_series": [["COMPUTED_RATIO", "ratio", "ratio"]],
        "observations": [
            obs("NUMER", "USA", 2000, 3), obs("DENOM", "USA", 2000, 4),
            obs("NUMER", "MYS", 2000, 3), obs("DENOM", "MYS", 2000, 0),
            obs("NUMER", "KEN", 2000, 9), obs("DENOM", "KEN", 2000, 2),
        ],
    })

    # 8. Score function returning None for some groups.
    cases.append({
        "name": "score_function_returns_none",
        "indicator_code": "NONEIN",
        "score_function": "none_below_fifty",
        "unit": "Sum",
        "computed_series": [],
        "observations": [
            obs("DATASET_A", "USA", 2020, 30), obs("DATASET_B", "USA", 2020, 80),
            obs("DATASET_A", "MYS", 2020, 70), obs("DATASET_B", "MYS", 2020, 5),
        ],
    })

    # 9. Value function returning a non-numeric value for some groups (veto).
    cases.append({
        "name": "computed_series_non_numeric_veto",
        "indicator_code": "TEXTVL",
        "score_function": "uses_maybe_text",
        "unit": "Index",
        "computed_series": [["COMPUTED_MAYBE_TEXT", "maybe", "maybe_text"]],
        "observations": [obs("DATASET_A", "USA", 2020, 80), obs("DATASET_A", "MYS", 2020, 20)],
    })

    # 10. Callable unit + extreme magnitudes + a group with extra dataset only.
    cases.append({
        "name": "callable_unit_extreme_values",
        "indicator_code": "EXTREM",
        "score_function": "two_dataset_average",
        "unit": {"function": "high_low_unit"},
        "computed_series": [],
        "observations": [
            obs("DATASET_A", "USA", 2020, 1e10), obs("DATASET_B", "USA", 2020, 1e-10),
            obs("DATASET_A", "MYS", 2020, -7.25), obs("DATASET_B", "MYS", 2020, 1e15),
            obs("DATASET_C", "KEN", 2020, 1),  # neither required dataset -> incomplete
        ],
    })

    # 11. Groups arriving out of order across countries and years; order must be first-seen.
    cases.append({
        "name": "first_seen_group_order",
        "indicator_code": "ORDERS",
        "score_function": "plain_sum",
        "unit": "Sum",
        "computed_series": [],
        "observations": [
            obs("DATASET_B", "MYS", 2021, 1), obs("DATASET_A", "USA", 2020, 2),
            obs("DATASET_A", "MYS", 2021, 3), obs("DATASET_B", "USA", 2020, 4),
            obs("DATASET_A", "USA", 2019, 5), obs("DATASET_B", "USA", 2019, 6),
        ],
    })
    return cases


def run_old(case: dict, functions: dict) -> dict:
    from sspi_flask_app.api.resources.utilities import score_indicator

    unit = case["unit"]
    unit_arg = functions["unit"][unit["function"]] if isinstance(unit, dict) else unit
    spec = [(code, u, functions["value"][fn]) for code, u, fn in case["computed_series"]]
    complete, incomplete = score_indicator(
        copy.deepcopy(case["observations"]),
        case["indicator_code"],
        score_function=functions["score"][case["score_function"]],
        unit=unit_arg,
        compute_series_specification=spec,
    )
    for doc in complete + incomplete:
        for ds in doc.get("Datasets", []):
            ds.pop("ValueFunction", None)  # source-text provenance is deliberately not ported
    return {"complete": complete, "incomplete": incomplete}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-repo", default=os.path.abspath(os.path.join(HERE, "..", "..", "..", "sspi-data-webapp")))
    parser.add_argument("--out", default=os.path.join(HERE, "scoring_cases.json"))
    args = parser.parse_args()

    from sspi_flask_app.api.resources.utilities import goalpost as old_goalpost

    functions = make_functions(old_goalpost)
    commit = subprocess.check_output(["git", "-C", args.old_repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", args.old_repo, "status", "--porcelain"], text=True).strip())

    cases = []
    for case in build_cases():
        expected = run_old(case, functions)
        cases.append({**case, "expected": expected})

    payload = {
        "generated_from": {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": platform.python_version(),
            "source_function": "sspi_flask_app.api.resources.utilities.score_indicator",
        },
        "cases": cases,
    }
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
    print(f"wrote {len(cases)} cases to {args.out} from commit {commit}{' (dirty)' if dirty else ''}")


if __name__ == "__main__":
    main()
