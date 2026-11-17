"""Generate the aggregation goldens from the OLD implementation.

Runs the legacy ``finalize_sspi_dynamic_score_iterator``
(sspi_flask_app/api/core/finalize.py) unchanged: its ``DataCoverage`` picks
the indicators with complete SSPI67 x 2000-2023 coverage, ``item_details``
prunes the methodology tree to them, and the ``SSPI`` class averages each
(country, year) into category, pillar and SSPI scores, which the route writes
to ``sspi_item_data``.

Only storage is replaced. Each legacy collection wrapper keeps its own class
(so ``sspi_item_data`` still validates every document it inserts); its pymongo
collection is swapped for :class:`Collection`, an in-memory collection that
answers exactly the queries and the two aggregation pipelines the route
issues, and refuses anything else. The methodology tree is the legacy one,
built by the legacy ``load_methodology_files`` / ``build_children_fields`` /
``sort_item_details`` from the pinned repository's ``methodology/`` directory.

Two goldens:

* ``aggregation_cases.json``: synthetic scenarios (fixed seed, inputs written
  into the golden): partial coverage, a dropped category and a dropped pillar,
  scores outside the window, a non-member country, an unknown indicator code,
  a NULL score, an observed/imputed collision, nothing complete.
* ``aggregation_on_production_cases.json`` (with ``--snapshot``): production's
  own indicator scores (``sspi_indicator_data`` + ``sspi_imputed_data`` from
  the private 2026-11-09 snapshot, SSPI67 x 2000-2023 only, which is all the
  route reads) through the legacy route, plus every aggregate where
  production's stored ``sspi_item_data`` differs from the legacy output.

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=<backend>/tests/golden env/bin/python <backend>/tests/golden/generate_aggregation_cases.py \\
        [--snapshot <backend>/local-data/production/2026-11-09]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import types
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
WINDOW = range(2000, 2024)
SEED = 20261116

# --------------------------------------------------------------------------- #
# In-memory pymongo collection
# --------------------------------------------------------------------------- #

COLLECTIONS: dict[str, "Collection"] = {}


def _get(document, dotted):
    for key in dotted.split("."):
        if not isinstance(document, dict) or key not in document:
            return _MISSING
        document = document[key]
    return document


_MISSING = object()


def _matches(document, query):
    for key, wanted in query.items():
        value = _get(document, key)
        if isinstance(wanted, dict):
            for operator, operand in wanted.items():
                if operator == "$in":
                    ok = value is not _MISSING and value in operand
                elif operator == "$gte":
                    ok = value is not _MISSING and value >= operand
                elif operator == "$lte":
                    ok = value is not _MISSING and value <= operand
                elif operator == "$regex":
                    flags = re.IGNORECASE if "i" in wanted.get("$options", "") else 0
                    ok = isinstance(value, str) and re.search(operand, value, flags) is not None
                elif operator == "$options":
                    ok = True
                else:
                    raise AssertionError(f"query operator {operator} is not used by the stubbed route")
                if not ok:
                    return False
        elif value is _MISSING or value != wanted:
            return False
    return True


class Collection:
    """The subset of a pymongo collection the legacy aggregation route uses."""

    def __init__(self, name, documents=()):
        self.name = name
        self.documents = [json.loads(json.dumps(d)) for d in documents]
        COLLECTIONS[name] = self

    def find(self, query, options=None):
        return [json.loads(json.dumps(d)) for d in self.documents if _matches(d, query)]

    def find_one(self, query, options=None):
        found = self.find(query)
        return found[0] if found else None

    def count_documents(self, query):
        return len(self.find(query))

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [d for d in self.documents if not _matches(d, query)]
        return types.SimpleNamespace(deleted_count=before - len(self.documents))

    def insert_many(self, documents):
        self.documents.extend(json.loads(json.dumps(documents)))
        return types.SimpleNamespace(inserted_ids=list(range(len(documents))))

    def aggregate(self, pipeline):
        return _run_pipeline(self.documents, pipeline)


def _run_pipeline(documents, pipeline):
    rows = [json.loads(json.dumps(d)) for d in documents]
    for stage in pipeline:
        (name, spec), = stage.items()
        if name == "$match":
            rows = [r for r in rows if _matches(r, spec)]
        elif name == "$unionWith":
            rows += _run_pipeline(COLLECTIONS[spec["coll"]].documents, spec["pipeline"])
        elif name == "$group":
            rows = _group(rows, spec)
        elif name == "$project":
            rows = [_project(r, spec) for r in rows]
        elif name == "$sort":
            for key, direction in reversed(list(spec.items())):
                assert direction == 1
                rows.sort(key=lambda r: r[key])
        else:
            raise AssertionError(f"pipeline stage {name} is not used by the stubbed route")
    return rows


def _expression(row, expression):
    if isinstance(expression, str) and expression.startswith("$"):
        return _get(row, expression[1:])
    if isinstance(expression, dict) and set(expression) == {"$cond"}:
        condition, then, otherwise = expression["$cond"]
        (operator, (left, right)), = condition.items()
        assert operator == "$gte"
        value = _expression(row, left)
        return _expression(row, then) if value is not _MISSING and value >= right else (
            _MISSING if otherwise == "$$REMOVE" else _expression(row, otherwise)
        )
    if isinstance(expression, dict):
        out = {}
        for key, sub in expression.items():
            value = _expression(row, sub)
            if value is not _MISSING:  # a missing field is left out, as Mongo does
                out[key] = value
        return out
    return expression


def _group(rows, spec):
    groups: dict[str, dict] = {}
    for row in rows:
        identity = _expression(row, spec["_id"])
        key = json.dumps(identity, sort_keys=True)
        group = groups.setdefault(key, {"_id": identity})
        for field, (accumulator, expression), in ((f, *e.items()) for f, e in spec.items() if f != "_id"):
            value = _expression(row, expression)
            if accumulator == "$push":
                group.setdefault(field, []).append(value)
            elif accumulator == "$addToSet":
                bucket = group.setdefault(field, [])
                if value is not _MISSING and value not in bucket:
                    bucket.append(value)
            else:
                raise AssertionError(f"accumulator {accumulator} is not used by the stubbed route")
    return list(groups.values())


def _project(row, spec):
    out = {}
    for key, expression in spec.items():
        if key == "_id" and expression == 0:
            continue
        if expression == 1:
            if key in row:
                out[key] = row[key]
            continue
        value = _expression(row, expression)
        if value is not _MISSING:
            out[key] = value
    return out


# --------------------------------------------------------------------------- #
# Running the legacy route
# --------------------------------------------------------------------------- #


def legacy_tree():
    """The pinned methodology tree as the legacy loader stores it, in insertion order."""
    import sys

    from sspi_flask_app.models.database import sspi_metadata

    # The package re-exports the wrapper instance under the module's own name, so reach the module itself.
    sys.modules["sspi_flask_app.models.database.sspi_metadata"].app = types.SimpleNamespace(instance_path=os.path.join(OLD_REPO, "instance"))
    details = sspi_metadata.build_children_fields(sspi_metadata.load_methodology_files())
    for detail in details:
        detail["DocumentType"] = detail["ItemType"] + "Detail"
    return sspi_metadata.sort_item_details(details)


def run_legacy(tree_documents, group_members, observed, imputed):
    """Feed the scores to the legacy route; return what it stored, or the exception it raised."""
    from sspi_flask_app.api.core.finalize import finalize_sspi_dynamic_score_iterator
    from sspi_flask_app.models.coverage import DataCoverage
    from sspi_flask_app.models.database import sspi_imputed_data, sspi_indicator_data, sspi_item_data, sspi_metadata

    COLLECTIONS.clear()
    group = {"DocumentType": "CountryGroup", "Metadata": {"CountryGroupName": "SSPI67", "Countries": group_members}}
    sspi_metadata._mongo_database = Collection("sspi_metadata", tree_documents + [group])
    sspi_indicator_data._mongo_database = Collection("sspi_indicator_data", observed)
    sspi_imputed_data._mongo_database = Collection("sspi_imputed_data", imputed)
    sspi_item_data._mongo_database = Collection("sspi_item_data", [{"ItemCode": "STALE", "CountryCode": "XXX", "Year": 1999, "Score": 0.5}])

    # The arguments finalize_iterator passes: DataCoverage(2000, 2023, "SSPI67").
    coverage = DataCoverage(2000, 2023, "SSPI67")
    complete = coverage.complete()
    try:
        messages = list(finalize_sspi_dynamic_score_iterator(complete, list(coverage.country_codes)))
    except Exception as exc:  # recorded, not hidden: the golden says the legacy route raised
        return {"complete_indicators": complete, "error": {"type": type(exc).__name__, "message": str(exc)[:400]},
                "item_data_after": len(COLLECTIONS["sspi_item_data"].documents)}
    return {"complete_indicators": complete, "messages": messages, "items": COLLECTIONS["sspi_item_data"].documents}


# --------------------------------------------------------------------------- #
# Synthetic scenarios
# --------------------------------------------------------------------------- #


def _rows(rng, indicator, countries, years, *, imputed_every=0):
    observed, imputed = [], []
    for i, (country, year) in enumerate((c, y) for c in countries for y in years):
        row = {"IndicatorCode": indicator, "CountryCode": country, "Year": year, "Score": rng.random(), "Unit": "Index"}
        (imputed if imputed_every and i % imputed_every == 0 else observed).append(row)
    return observed, imputed


def synthetic_scenarios():
    members = ["USA", "FRA", "KEN"]
    full = list(WINDOW)

    def base(rng):
        observed, imputed = [], []

        def add(indicator, countries=members, years=full, imputed_every=0):
            o, i = _rows(rng, indicator, countries, years, imputed_every=imputed_every)
            observed.extend(o)
            imputed.extend(i)

        add("BIODIV", imputed_every=5)                       # complete, partly imputed
        add("REDLST", years=[1998, 1999] + full + [2024])     # complete; rows outside the window
        add("NITROG")                                        # complete
        add("WATMAN", years=[y for y in full if y != 2011])   # incomplete: 2011 missing everywhere
        add("CHMPOL", imputed_every=3)                       # complete, partly imputed
        add("GTRANS", countries=["USA", "FRA"])              # incomplete: KEN missing -> GHG dropped
        add("ALTNRG")                                        # complete (NRG with one indicator)
        add("NRGINT", imputed_every=7)                       # complete
        add("AIRPOL")                                        # complete
        add("EMPLOY", countries=["USA"])                     # incomplete -> whole MS pillar dropped
        add("ENRPRI")                                        # EDU: four complete indicators
        add("ENRSEC", imputed_every=4)
        add("YRSEDU")
        add("PUPTCH")
        add("MURDER", imputed_every=2)                       # SAF: one of four
        add("BIODIV", countries=["BRA"])                     # a non-member country
        add("ZZZTST")                                        # a code that is not in the methodology
        return observed, imputed

    scenarios = []
    rng = random.Random(SEED)
    observed, imputed = base(rng)
    for row in observed:  # exact ones and zeros, as production stores them (ints)
        if row["IndicatorCode"] == "YRSEDU" and row["Year"] % 4 == 0:
            row["Score"] = 1
        if row["IndicatorCode"] == "ALTNRG" and row["Year"] % 5 == 0:
            row["Score"] = 0
    scenarios.append(("partial_coverage", members, observed, imputed))

    rng = random.Random(SEED)
    observed, imputed = base(rng)
    next(r for r in observed if r["IndicatorCode"] == "NITROG" and r["CountryCode"] == "FRA" and r["Year"] == 2010)["Score"] = None
    scenarios.append(("null_score_in_complete_indicator", members, observed, imputed))

    rng = random.Random(SEED)
    observed, imputed = base(rng)
    duplicate = dict(next(r for r in observed if r["IndicatorCode"] == "NITROG" and r["CountryCode"] == "KEN" and r["Year"] == 2005))
    imputed.append({**duplicate, "Score": 0.25})
    scenarios.append(("observed_and_imputed_collision", members, observed, imputed))

    rng = random.Random(SEED)
    observed, imputed = _rows(rng, "BIODIV", ["USA", "FRA"], full)
    scenarios.append(("nothing_complete", members, observed, imputed))
    return scenarios


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def aggregate_records(items):
    """Stored category, pillar and SSPI documents, in insertion order."""
    return [
        {"item_code": d["ItemCode"], "item_type": d["ItemType"], "country_code": d["CountryCode"], "year": d["Year"],
         "score": d["Score"], "children": d.get("Children"), "item_name": d.get("ItemName")}
        for d in items if d["ItemType"] != "Indicator"
    ]


def write(path, payload):
    """Write a golden file, keeping the existing one where only ``generated_at`` would change."""
    if os.path.exists(path):
        with open(path) as fh:
            existing = json.load(fh)
        strip = lambda p: {**p, "generated_from": {**p["generated_from"], "generated_at": None}}  # noqa: E731
        if strip(existing) == json.loads(json.dumps(strip(payload))):
            return
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, allow_nan=False)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", help="local-data/production/<date> directory (private); omit to skip the production golden")
    args = parser.parse_args()

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    tree_documents = legacy_tree()

    def generated_from(fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": [
                "sspi_flask_app/api/core/finalize.py:finalize_sspi_dynamic_score_iterator",
                "sspi_flask_app/models/coverage.py:DataCoverage",
                "sspi_flask_app/models/database/sspi_metadata.py:SSPIMetadata.item_details",
                "sspi_flask_app/models/sspi.py:SSPI",
            ],
            "fixture": fixture,
        }

    tree = [
        {"code": d["Metadata"]["ItemCode"], "item_type": d["Metadata"]["ItemType"], "children": d["Metadata"]["Children"]}
        for d in tree_documents if d["Metadata"]["ItemType"] != "Indicator"
    ]
    cases = []
    for name, members, observed, imputed in synthetic_scenarios():
        outcome = run_legacy(tree_documents, members, observed, imputed)
        case = {"name": name, "group_members": members, "observed": observed, "imputed": imputed,
                "complete_indicators": outcome["complete_indicators"]}
        if "error" in outcome:
            case["legacy_error"] = outcome["error"]
            case["item_data_after_error"] = outcome["item_data_after"]
        else:
            case["indicator_rows_stored"] = sum(1 for d in outcome["items"] if d["ItemType"] == "Indicator")
            case["aggregates"] = aggregate_records(outcome["items"])
        cases.append(case)
    write(os.path.join(HERE, "aggregation_cases.json"), {
        "generated_from": generated_from("synthetic, written into this file (seed %d)" % SEED),
        "legacy_tree": tree,
        "cases": cases,
    })

    if args.snapshot:
        write_production(args.snapshot, tree_documents, generated_from)


def write_production(snapshot, tree_documents, generated_from):
    def load(name):
        path = os.path.join(snapshot, f"{name}.json")
        with open(path, "rb") as fh:
            raw = fh.read()
        return json.loads(raw), hashlib.sha256(raw).hexdigest()

    members = next(g for g in json.load(open(os.path.join(NEW_REPO, "tests", "golden", "country_cases.json")))["groups"]
                   if g["code"] == "SSPI67")["members"]
    observed_all, observed_sha = load("sspi_indicator_data")
    imputed_all, imputed_sha = load("sspi_imputed_data")
    items_all, items_sha = load("sspi_item_data")
    keep = lambda r: r["CountryCode"] in members and r["Year"] in WINDOW  # noqa: E731  (all the route reads)
    fields = ("IndicatorCode", "CountryCode", "Year", "Score")
    observed = [{f: r[f] for f in fields} for r in observed_all if keep(r)]
    imputed = [{f: r[f] for f in fields} for r in imputed_all if keep(r)]
    outcome = run_legacy(tree_documents, members, observed, imputed)
    assert "error" not in outcome, outcome
    legacy = aggregate_records(outcome["items"])

    production = {(d["ItemCode"], d["CountryCode"], d["Year"]): d["Score"] for d in items_all if d["ItemType"] != "Indicator"}
    legacy_by = {(r["item_code"], r["country_code"], r["year"]): r["score"] for r in legacy}
    assert set(production) == set(legacy_by), "production and legacy aggregate different identities"
    differences = [
        {"item_code": k[0], "country_code": k[1], "year": k[2], "legacy": legacy_by[k], "production": production[k]}
        for k in sorted(legacy_by) if legacy_by[k] != production[k]
    ]

    def compact(rows):
        out: dict[str, dict[str, list]] = {}
        for r in rows:
            out.setdefault(r["IndicatorCode"], {}).setdefault(r["CountryCode"], []).append([r["Year"], r["Score"]])
        for by_country in out.values():
            for series in by_country.values():
                series.sort()
        return out

    write(os.path.join(HERE, "aggregation_on_production_cases.json"), {
        "generated_from": generated_from("local-data/production/2026-11-09 (private; checksums below)"),
        "snapshot": {"date": "2026-11-09", "sha256": {"sspi_indicator_data": observed_sha, "sspi_imputed_data": imputed_sha, "sspi_item_data": items_sha},
                     "rows_kept": "SSPI67 x 2000-2023, the only rows the legacy route reads"},
        "group_members": members,
        "observed": compact(observed),
        "imputed": compact(imputed),
        "complete_indicators": outcome["complete_indicators"],
        "aggregates": {"columns": ["item_code", "item_type", "country_code", "year", "score"],
                       "rows": [[r["item_code"], r["item_type"], r["country_code"], r["year"], r["score"]] for r in legacy]},
        "production_differences": differences,
    })


if __name__ == "__main__":
    main()
