"""Shared pieces of the legacy-versus-new parity tests.

The model, for every migrated dataset and indicator:

    legacy backend at the pinned commit
        -> generate_*.py, run once in the legacy virtualenv
        -> committed golden JSON next to this file
        -> offline test replaying the SAME committed source fixture
           through the new backend and comparing records

Normal test runs need neither the legacy repository nor a network.

Comparison is exact equality, floats included: both sides run the same
arithmetic in the same order on the same inputs, so any difference is a real
difference. No tolerance is applied anywhere. If a future indicator needs
one, pass it explicitly at that call site and document why in
``docs/indicator-migration.md``.

This module is deliberately small: two registers, a loader, record builders
and one comparison that explains what differs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
PINNED_LEGACY_REPOSITORY = "sspi-data-webapp"
PINNED_LEGACY_COMMIT = "76f842b08e551dfa8fb9563e4c812be086654ba6"

# The registers. A dataset is not ingestible and an indicator is not
# executable without an entry here; test_migration_gate.py enforces it.
OBSERVATION_CASES: dict[str, str] = {
    "UNSDG_MARINE": "unsdg_marine_cases.json",
    "UNSDG_TERRST": "unsdg_terrst_cases.json",
    "UNSDG_FRSHWT": "unsdg_frshwt_cases.json",
    "UNSDG_REDLST": "unsdg_redlst_cases.json",
    "UNSDG_STKHLM": "unsdg_stkhlm_cases.json",
    "UNSDG_MINMAT": "unsdg_minmat_cases.json",
    "UNSDG_MONTRL": "unsdg_montrl_cases.json",
    "UNSDG_BASELA": "unsdg_basela_cases.json",
    "UNSDG_ROTDAM": "unsdg_rotdam_cases.json",
    "UNSDG_WTSTRS": "unsdg_wtstrs_cases.json",
    "UNSDG_WUSEFF": "unsdg_wuseff_cases.json",
    "UNSDG_CWUEFF": "unsdg_cwueff_cases.json",
}
INDICATOR_CASES: dict[str, str] = {
    "BIODIV": "biodiv_imputation_cases.json",
    "REDLST": "redlst_cases.json",
    "CHMPOL": "chmpol_cases.json",
}

OBSERVATION_IDENTITY = ("country_code", "year")
SCORE_IDENTITY = ("country_code", "year")
IMPUTATION_FIELDS = ("imputed", "imputation_method", "imputation_distance")


def load_cases(filename: str) -> dict[str, Any]:
    """A committed golden file, verified to come from the pinned legacy commit."""
    payload = json.loads((HERE / filename).read_text())
    assert_pinned(payload, filename)
    return payload


def assert_pinned(payload: dict[str, Any], name: str) -> None:
    meta = payload.get("generated_from") or {}
    assert meta.get("repository") == PINNED_LEGACY_REPOSITORY, f"{name}: not generated from {PINNED_LEGACY_REPOSITORY}"
    assert meta.get("commit") == PINNED_LEGACY_COMMIT, f"{name}: generated from {meta.get('commit')}, not the pinned commit {PINNED_LEGACY_COMMIT}"
    assert meta.get("working_tree_dirty") is False, f"{name}: generated from a dirty legacy working tree"


def source_fixtures(payload: dict[str, Any]) -> list[Path]:
    """The committed source snapshot(s) the golden file was generated from."""
    meta = payload["generated_from"]
    names = meta.get("fixtures") or [meta["fixture"]]
    return [REPO_ROOT / name if "/" in name else REPO_ROOT / "tests" / "fixtures" / "unsdg" / name for name in names]


def observation_record(observation: Any) -> dict[str, Any]:
    return {"country_code": observation.country_code, "year": observation.year, "value": observation.value, "unit": observation.unit}


def input_record(observation: Any, *, imputation: bool) -> dict[str, Any]:
    record = {"dataset_code": observation.dataset_code, "value": observation.value, "unit": observation.unit}
    if imputation:
        record = {
            "dataset_code": observation.dataset_code,
            "country_code": observation.country_code,
            "year": observation.year,
            "value": observation.value,
            "unit": observation.unit,
            "imputed": bool(observation.provenance.get("imputed", False)),
            "imputation_method": observation.provenance.get("imputation_method"),
            "imputation_distance": observation.provenance.get("imputation_distance"),
        }
    return record


def score_records(scores: Iterable[Any], *, imputation: bool) -> list[dict[str, Any]]:
    """Scores as golden-file records, sorted by identity. ``imputation=True``
    adds each input's identity and imputation fields, for indicators whose
    legacy implementation imputes."""
    return [
        {
            "country_code": s.country_code,
            "year": s.year,
            "score": s.score,
            "unit": s.unit,
            "inputs": sorted((input_record(o, imputation=imputation) for o in s.inputs), key=lambda r: r["dataset_code"]),
        }
        for s in sorted(scores, key=lambda s: (s.country_code, s.year))
    ]


def summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    years = [r["year"] for r in records]
    return {"count": len(records), "countries": sorted({r["country_code"] for r in records}), "years": (min(years), max(years)) if years else None}


def assert_parity(what: str, new: Sequence[dict[str, Any]], legacy: Sequence[dict[str, Any]], identity: Sequence[str] = SCORE_IDENTITY) -> None:
    """Exact parity of two record lists, with a failure message that says
    which identities are missing, which are extra and which fields differ.

    Both lists must already be in identity order, so order is compared too.
    """

    def key(record: dict[str, Any]) -> tuple:
        return tuple(record[name] for name in identity)

    new_by, legacy_by = {key(r): r for r in new}, {key(r): r for r in legacy}
    problems: list[str] = []
    if len(new_by) != len(new):
        problems.append(f"new backend produced {len(new) - len(new_by)} duplicate identities")
    if len(legacy_by) != len(legacy):
        problems.append(f"golden file holds {len(legacy) - len(legacy_by)} duplicate identities")
    missing, extra = sorted(set(legacy_by) - set(new_by)), sorted(set(new_by) - set(legacy_by))
    if missing:
        problems.append(f"{len(missing)} identities in legacy but not produced: {missing[:10]}")
    if extra:
        problems.append(f"{len(extra)} identities produced but not in legacy: {extra[:10]}")
    differing = [k for k in sorted(set(new_by) & set(legacy_by)) if new_by[k] != legacy_by[k]]
    for k in differing[:10]:
        fields = sorted(f for f in set(new_by[k]) | set(legacy_by[k]) if new_by[k].get(f) != legacy_by[k].get(f))
        problems.append(f"{k} differs in {fields}: " + "; ".join(f"{f} new={new_by[k].get(f)!r} legacy={legacy_by[k].get(f)!r}" for f in fields))
    if len(differing) > 10:
        problems.append(f"... and {len(differing) - 10} more differing identities")
    if not problems and list(new) != list(legacy):
        problems.append("same records in a different order")
    assert not problems, f"{what}: legacy parity broken (new {summary(new)}, legacy {summary(legacy)})\n  - " + "\n  - ".join(problems)
