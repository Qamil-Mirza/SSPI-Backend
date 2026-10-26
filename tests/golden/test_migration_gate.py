"""The migration gate: nothing is ingestible or executable without committed
legacy parity evidence from the pinned commit and a row in the register.

See docs/indicator-migration.md.
"""

import json
import re

import pytest

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from tests.golden.parity import (
    APPROVED_SOURCE_CORRECTIONS,
    APPROVED_STORAGE_CORRECTIONS,
    HERE,
    INDICATOR_CASES,
    INOPERATIVE_IMPUTE_ROUTES,
    INTENTIONAL_DIVERGENCES,
    OBSERVATION_CASES,
    OBSERVED_ONLY_EXECUTIONS,
    PENDING_METHODOLOGY_DECISIONS,
    PROPOSED_SOURCE_CORRECTIONS,
    REPO_ROOT,
    RESOLVED_METHODOLOGY_DECISIONS,
    assert_pinned,
    legacy_failure,
    legacy_output_conflict,
    load_cases,
    source_fixtures,
)

DOCS = REPO_ROOT / "docs"
CONFLICTS = (DOCS / "methodology-conflicts.md").read_text()
MIGRATION = (DOCS / "indicator-migration.md").read_text()
ENTRY = re.compile(r"^## ([A-Z0-9_]+-\d+) — (.+)$", re.MULTILINE)
STATUSES = {"unresolved", "reviewed", "resolved"}
REQUIRED_SECTIONS = (
    "Current executable behavior",
    "Conflicting evidence:",
    "Implementation decision in the new backend:",
    "Reason:",
    "Potential impact:",
    "Question for methodology review:",
    "Relevant legacy files:",
    "Relevant new-backend files:",
)


def entries() -> dict[str, str]:
    """Conflict ID -> entry text."""
    found = {}
    for match in ENTRY.finditer(CONFLICTS):
        following = re.search(r"^## ", CONFLICTS[match.end() :], re.MULTILINE)  # next entry, or the template section
        found[match.group(1)] = CONFLICTS[match.start() : match.end() + following.start() if following else len(CONFLICTS)]
    return found


def register_row(code: str) -> list[str]:
    rows = [line for line in MIGRATION.splitlines() if line.startswith(f"| {code} |")]
    assert len(rows) == 1, f"{code}: expected exactly one register row in docs/indicator-migration.md, found {len(rows)}"
    return [cell.strip() for cell in rows[0].strip("|").split("|")]


@pytest.mark.parametrize("path", sorted(HERE.glob("*_cases.json")), ids=lambda p: p.name)
def test_every_golden_file_comes_from_the_pinned_legacy_commit(path):
    assert_pinned(json.loads(path.read_text()), path.name)


def test_every_ingestible_dataset_has_observation_parity():
    """Observation parity evidence exists for exactly the ingestible datasets plus the datasets whose legacy source is
    gone (historical parity only); a dataset is never both."""
    assert not set(SUPPORTED_DATASETS) & set(UNAVAILABLE_SOURCES)
    assert set(SUPPORTED_DATASETS) | set(UNAVAILABLE_SOURCES) == set(OBSERVATION_CASES)


@pytest.mark.parametrize("code", sorted(UNAVAILABLE_SOURCES))
def test_an_unavailable_source_is_declared_in_the_register(code):
    """The register row of a dataset with no live source says so, and so does the section listing such indicators."""
    assert "live source unavailable" in register_row(code)[4]
    readers = sorted(i for i in registry.codes() if code in registry.get(i).dataset_codes)
    section = MIGRATION.split("### Historical parity only: live source unavailable", 1)[1].split("\n## ", 1)[0]
    assert readers and all(f"`{i}`" in section for i in readers) and f"`{code}`" in section


def test_every_executable_indicator_has_score_parity():
    assert set(registry.codes()) == set(INDICATOR_CASES)


@pytest.mark.parametrize("code", sorted(OBSERVATION_CASES))
def test_dataset_evidence_is_committed_and_registered(code):
    case = load_cases(OBSERVATION_CASES[code])
    assert case["dataset_code"] == code
    assert all(path.exists() for path in source_fixtures(case))
    row = register_row(code)
    assert OBSERVATION_CASES[code] in row[2] and all(str(path.relative_to(REPO_ROOT)) in row[1] for path in source_fixtures(case))


@pytest.mark.parametrize("code", sorted(INDICATOR_CASES))
def test_indicator_evidence_is_committed_and_registered(code):
    case = load_cases(INDICATOR_CASES[code])
    assert all(path.exists() for path in source_fixtures(case))
    row = register_row(code)
    assert INDICATOR_CASES[code] in row[1]
    assert row[3] == ("yes" if registry.get(code).imputes else "no")
    documented = sorted(i for i in entries() if i.rsplit("-", 1)[0] == code)
    listed = [] if row[4] == "none known" else [c.strip() for c in row[4].split(",")]
    assert listed == documented, f"{code}: register lists {listed}, methodology-conflicts.md documents {documented}"


def _variants():
    for code, filename in INDICATOR_CASES.items():
        for variant in load_cases(filename).get("variants", []):
            yield code, variant


def test_legacy_failures_are_registered_divergences_and_nothing_else_is():
    """A golden variant where the legacy route raised must be an explicitly registered divergence with an APPROVED
    policy; a registered divergence must correspond to such a variant; every other variant is held to exact parity
    or is a pending decision (next test)."""
    failures = {(code, v["name"]) for code, v in _variants() if legacy_failure(v)}
    assert failures == set(INTENTIONAL_DIVERGENCES), f"legacy failures {sorted(failures)} vs registered divergences {sorted(INTENTIONAL_DIVERGENCES)}"
    documented = entries()
    for key, conflict in INTENTIONAL_DIVERGENCES.items():
        assert conflict in documented, f"{key}: divergence cites {conflict}, which is not in docs/methodology-conflicts.md"
        assert "Implementation policy" in documented[conflict], f"{conflict}: a divergence entry must state the implementation policy adopted"
        assert f"`{key[1]}`" in MIGRATION and conflict in MIGRATION, f"{key}: divergence must be listed in docs/indicator-migration.md"


def test_legacy_output_conflicts_are_pending_or_resolved_decisions():
    """A golden variant where the legacy route stored more than one score for an identity is a methodology decision,
    registered exactly once: PENDING (pointing at an UNRESOLVED entry that lays out the options without adopting one; the
    new backend raises there) or RESOLVED (pointing at a RESOLVED entry with cited evidence; the indicator's golden test
    holds the decided result exactly). It is never registered as a divergence."""
    conflicts = {(code, v["name"]) for code, v in _variants() if legacy_output_conflict(v)}
    registered = set(PENDING_METHODOLOGY_DECISIONS) | set(RESOLVED_METHODOLOGY_DECISIONS)
    assert conflicts == registered, f"legacy output conflicts {sorted(conflicts)} vs registered decisions {sorted(registered)}"
    assert not set(PENDING_METHODOLOGY_DECISIONS) & set(RESOLVED_METHODOLOGY_DECISIONS)
    assert not registered & set(INTENTIONAL_DIVERGENCES)
    documented = entries()
    for key, conflict in PENDING_METHODOLOGY_DECISIONS.items():
        assert conflict in documented, f"{key}: pending decision cites {conflict}, which is not in docs/methodology-conflicts.md"
        text = documented[conflict]
        assert "Status: unresolved" in text, f"{conflict}: a pending decision must be unresolved"
        assert "Potential direction A" in text and "Potential direction B" in text, f"{conflict}: must lay out the options for the methodology team"
        assert "Implementation policy adopted" not in text, f"{conflict}: a pending decision must not claim an adopted policy"
        assert f"`{key[1]}`" in MIGRATION and conflict in MIGRATION, f"{key}: pending decision must be listed in docs/indicator-migration.md"
    for key, conflict in RESOLVED_METHODOLOGY_DECISIONS.items():
        assert conflict in documented, f"{key}: resolved decision cites {conflict}, which is not in docs/methodology-conflicts.md"
        text = documented[conflict]
        assert "Status: resolved" in text and "Resolution evidence:" in text, f"{conflict}: a resolved decision must be resolved with cited evidence"
        assert f"`{key[1]}`" in MIGRATION and conflict in MIGRATION, f"{key}: resolved decision must be listed in docs/indicator-migration.md"


def test_inoperative_legacy_impute_routes_are_registered_and_reproduced_without_imputation():
    """An indicator whose legacy impute route raised on the committed fixture as a whole (top-level
    ``legacy_impute_error``) is registered in INOPERATIVE_IMPUTE_ROUTES, and only then. The golden file must show the
    route raising on the fixture, on an empty dataset and on the probe written for the route's own schema, and
    leaving no imputed score behind; the new backend then has no imputation strategy, so it stores exactly what
    legacy stored. The cited entry is unresolved and lays out the options without adopting one."""
    failing = {code for code, filename in INDICATOR_CASES.items() if load_cases(filename).get("legacy_impute_error")}
    assert failing == set(INOPERATIVE_IMPUTE_ROUTES), f"top-level legacy impute failures {sorted(failing)} vs registered {sorted(INOPERATIVE_IMPUTE_ROUTES)}"
    assert not set(INOPERATIVE_IMPUTE_ROUTES) & {code for code, _ in list(INTENTIONAL_DIVERGENCES) + list(PENDING_METHODOLOGY_DECISIONS) + list(RESOLVED_METHODOLOGY_DECISIONS)}
    documented = entries()
    for code, conflict in INOPERATIVE_IMPUTE_ROUTES.items():
        case = load_cases(INDICATOR_CASES[code])
        assert case["impute_route_exists"] is True and case["imputed_scores"] == [], code
        runs = case["impute_route"]
        assert set(runs) == {"fixture", "empty_dataset", "legacy_schema_probe"}, f"{code}: the route must be shown failing on every recorded state"
        for name, outcome in runs.items():
            assert outcome["legacy_impute_error"], f"{code}: the legacy impute route completed on {name}"
            assert not [d for d in outcome["imputed_collection_after"] if d.get("IndicatorCode") == code], f"{code}: the route left imputed scores on {name}"
        assert runs["fixture"]["legacy_impute_error"] == case["legacy_impute_error"] == case["empty_dataset"]["legacy_impute_error"]
        assert not registry.get(code).imputes, f"{code}: an inoperative legacy impute route is reproduced by having no imputation strategy"
        assert registry_row_imputes(code) == "no"
        assert conflict in documented, f"{code}: cites {conflict}, which is not in docs/methodology-conflicts.md"
        text = documented[conflict]
        assert "Status: unresolved" in text and "Potential direction A" in text and "Potential direction B" in text, f"{conflict}: must be unresolved and lay out the options"
        assert "Implementation policy adopted" not in text, f"{conflict}: must not claim an adopted policy"
        section = MIGRATION.split("## Inoperative legacy impute routes", 1)[1].split("\n## ", 1)[0]
        assert f"`{code}`" in section and conflict in section, f"{code}: must be listed under 'Inoperative legacy impute routes' in docs/indicator-migration.md"


def test_observed_only_executions_are_registered_both_ways_and_keep_the_legacy_route_testable():
    """An indicator whose legacy impute route works on the committed fixture but whose registered definition imputes
    nothing is registered in OBSERVED_ONLY_EXECUTIONS, and only then. The golden file must show the route succeeding on
    the fixture and failing on the recorded probe of the current situation; the preserved legacy strategy must exist and
    differ from the registered one (which is None); the approval must be confirmed; the cited entry must stay unresolved,
    record the approved treatment and adopt no policy; the migration doc and register row must say so."""
    import importlib

    observed_only = {
        code for code, filename in INDICATOR_CASES.items()
        if load_cases(filename).get("impute_route_exists") and not registry.get(code).imputes and code not in INOPERATIVE_IMPUTE_ROUTES
    }
    assert observed_only == set(OBSERVED_ONLY_EXECUTIONS), f"observed-only definitions with a working legacy route {sorted(observed_only)} vs registered {sorted(OBSERVED_ONLY_EXECUTIONS)}"
    assert not set(OBSERVED_ONLY_EXECUTIONS) & set(INOPERATIVE_IMPUTE_ROUTES)
    documented = entries()
    section = MIGRATION.split("## Approved observed-only executions", 1)[1].split("\n## ", 1)[0]
    for code, registered in OBSERVED_ONLY_EXECUTIONS.items():
        case = load_cases(INDICATOR_CASES[code])
        assert case["legacy_impute_error"] is None and case["imputed_scores"] and legacy_output_conflict(case) is None, f"{code}: the legacy route must work on the fixture"
        assert case[registered.probe]["legacy_impute_error"], f"{code}: the probe must record the legacy failure"
        module, name = registered.legacy_imputation.rsplit(".", 1)
        legacy = getattr(importlib.import_module(module), name)
        assert legacy is not None and registry.get(code).imputation is None and registry_row_imputes(code) == "no", code
        assert registered.confirmed and registered.approval and registered.treatment, f"{code}: approval not confirmed"
        assert registered.conflict in documented, f"{code}: cites {registered.conflict}, which is not in docs/methodology-conflicts.md"
        text = documented[registered.conflict]
        assert "Status: unresolved" in text and "Approved execution treatment" in text and "Potential direction A" in text, f"{registered.conflict}: must stay unresolved and record the treatment"
        assert "Implementation policy adopted" not in text, f"{registered.conflict}: must not claim an adopted policy"
        assert f"`{code}`" in section and registered.conflict in section, f"{code}: must be listed under 'Approved observed-only executions' in docs/indicator-migration.md"


def test_approved_storage_corrections_are_registered_both_ways_and_keep_the_methodology_question_open():
    """An indicator whose legacy impute route inserts its scores into ``sspi_indicator_data`` is registered in
    APPROVED_STORAGE_CORRECTIONS, and only then. The golden file must show, from executed legacy code, that the route
    cleared ``sspi_imputed_data`` and filled the observed collection, that one compute-then-impute pass held no identity
    twice (so exact parity is required), that a second impute run held every imputed identity twice and that a later
    compute run erased the imputations. The approval must be confirmed; the cited correction entry must be resolved
    and record it; the cited open question must stay unresolved and adopt nothing; the migration doc must list both."""
    misdirected = {code for code, filename in INDICATOR_CASES.items() if load_cases(filename).get("impute_route_inserts_into") == "sspi_indicator_data"}
    assert misdirected == set(APPROVED_STORAGE_CORRECTIONS), f"golden files recording impute routes writing to the observed collection {sorted(misdirected)} vs registered {sorted(APPROVED_STORAGE_CORRECTIONS)}"
    documented = entries()
    section = MIGRATION.split("## Approved storage corrections", 1)[1].split("\n## ", 1)[0]
    for code, registered in APPROVED_STORAGE_CORRECTIONS.items():
        case = load_cases(INDICATOR_CASES[code])
        assert case["impute_route_clears"] == "sspi_imputed_data" and case["legacy_impute_error"] is None and case["imputed_scores"], code
        assert legacy_output_conflict(case) is None, f"{code}: one legacy pass must be consistent for parity to be required"
        imputed, observed = len(case["imputed_scores"]), len(case["observed_scores"])
        storage = case["legacy_storage"]
        assert storage["compute_then_impute"] == {"sspi_indicator_data": observed + imputed, "sspi_indicator_data_imputed": imputed, "sspi_indicator_data_identities_held_twice": 0, "sspi_imputed_data": 0}, code
        assert storage["then_impute_again"]["sspi_indicator_data_identities_held_twice"] == imputed and storage["then_impute_again"]["sspi_imputed_data"] == 0, code
        assert storage["then_compute_again"]["sspi_indicator_data_imputed"] == storage["impute_then_compute"]["sspi_indicator_data_imputed"] == 0, code
        assert all(all(i["imputed"] for i in s["inputs"]) for s in case["imputed_scores"]), f"{code}: the legacy rows must mark their inputs imputed"
        assert registry.get(code).imputes and registry_row_imputes(code) == "yes", code
        assert registered.confirmed and registered.approval and registered.treatment, f"{code}: approval not confirmed"
        assert registered.conflict in documented and registered.open_question in documented, f"{code}: cites {registered.conflict} / {registered.open_question}, not both in docs/methodology-conflicts.md"
        text = documented[registered.conflict]
        assert "Approved storage correction" in text and "Status: resolved" in text and "Resolution evidence:" in text, f"{registered.conflict}: must be resolved and record the approval"
        question = documented[registered.open_question]
        assert "Status: unresolved" in question and "Potential direction A" in question and "Potential direction B" in question, f"{registered.open_question}: must be unresolved and lay out the options"
        assert "Implementation policy adopted" not in question, f"{registered.open_question}: must not claim an adopted policy"
        assert f"`{code}`" in section and registered.conflict in section and registered.open_question in section, f"{code}: must be listed under 'Approved storage corrections' in docs/indicator-migration.md"


def approved_source_correction_problems(register, observation_cases, supported, goldens, documented, section, readers) -> list[str]:
    """Every way the approved source-correction register disagrees with the evidence; empty when the gate passes.

    ``goldens`` maps golden file names to their content, ``readers`` dataset codes to the registered indicators reading
    them. A dataset whose golden file records an approved name table must be registered, and only then. Each entry needs,
    from executed legacy code, what the legacy cleaner did (a clean failure on the source or a variant, the rows it
    dropped for exactly the corrected names, or the years and names it got wrong), exactly the registered table, the
    corrected rows, a confirmed approval and resolved cited entries recording it. A blocked entry keeps its dataset not
    ingestible and unread by any registered indicator while its blocking entry stays unresolved; an unblocked one must
    be ingestible with its golden file in OBSERVATION_CASES."""
    problems = []
    corrected = {}
    for name, case in goldens.items():
        if "approved_name_corrections" in case:
            corrected.setdefault(case["dataset_code"], set()).add(name)
    if set(corrected) != set(register):
        problems.append(f"golden files with approved corrections {sorted(corrected)} vs registered {sorted(register)}")
    for code, registered in register.items():
        filename = observation_cases.get(code) or registered.golden
        if not filename or (registered.golden is None) != (code in observation_cases):
            problems.append(f"{code}: the corrected golden file must be named once, in OBSERVATION_CASES or in the register")
            continue
        if filename not in corrected.get(code, set()):
            problems.append(f"{code}: {filename} does not record the approved name table")
            continue
        case = goldens[filename]
        failures = [case.get("legacy_clean_error")] + [v if isinstance(v, str) else v.get("legacy_error") for v in case.get("invalid_variants", {}).values()]
        dropped = {row["country_code"] for row in case.get("legacy_dropped_rows", [])}
        divergence = case.get("legacy_divergence", {})
        if not (any(f and f.startswith("InvalidDocumentFormatError") for f in failures) or dropped or divergence):
            problems.append(f"{code}: no recorded legacy behaviour")
        if not dropped <= {c for c in registered.name_corrections.values() if c}:
            problems.append(f"{code}: dropped rows of a country the name table does not repair")
        if dropped and {name: case.get("legacy_matcher_results", {}).get(name) for name in registered.name_corrections} != {name: name for name in registered.name_corrections}:
            problems.append(f"{code}: the legacy matcher must have failed on every corrected name")
        if divergence and not (set(divergence.get("names", {})) == set(registered.name_corrections) and all(v["approved"] == registered.name_corrections[n] and v["legacy_code"] != v["approved"] for n, v in divergence["names"].items())):
            problems.append(f"{code}: the recorded legacy divergence does not cover exactly the corrected names")
        if case["approved_name_corrections"] != registered.name_corrections:
            problems.append(f"{code}: golden name table differs from the register")
        if not (case.get("observations") or case.get("corrected_variants")):
            problems.append(f"{code}: no corrected rows")
        if not (registered.confirmed and registered.approval):
            problems.append(f"{code}: approval not confirmed")
        for conflict in (registered.conflict, *registered.related_conflicts):
            text = documented.get(conflict)
            if text is None:
                problems.append(f"{code}: cites {conflict}, which is not in docs/methodology-conflicts.md")
            elif not ("Approved source correction" in text and "Status: resolved" in text and "Resolution evidence:" in text):
                problems.append(f"{conflict}: must be resolved and record the approval")
        if registered.blocked_by:
            if code in supported or code in observation_cases or readers.get(code):
                problems.append(f"{code}: blocked by {registered.blocked_by}, so neither ingestible nor read by a registered indicator")
            if "Status: unresolved" not in documented.get(registered.blocked_by, ""):
                problems.append(f"{code}: {registered.blocked_by} must stay unresolved while it blocks the dataset")
            if registered.blocked_by not in section:
                problems.append(f"{code}: the blocking entry must be listed under 'Approved source-representation corrections'")
        elif code not in supported:
            problems.append(f"{code}: approved and unblocked, but not ingestible")
        if f"`{code}`" not in section or registered.conflict not in section:
            problems.append(f"{code}: must be listed under 'Approved source-representation corrections' in docs/indicator-migration.md")
    return problems


def approved_source_correction_evidence():
    goldens = {path.name: json.loads(path.read_text()) for path in sorted(HERE.glob("*_cases.json"))}
    readers = {}
    for indicator in INDICATOR_CASES:
        for code in registry.get(indicator).dataset_codes:
            readers.setdefault(code, []).append(indicator)
    section = MIGRATION.split("## Approved source-representation corrections", 1)[1].split("\n## ", 1)[0]
    return {"register": dict(APPROVED_SOURCE_CORRECTIONS), "observation_cases": dict(OBSERVATION_CASES), "supported": set(SUPPORTED_DATASETS), "goldens": goldens, "documented": entries(), "section": section, "readers": readers}


def test_approved_source_corrections_are_registered_both_ways_and_record_the_legacy_failure():
    """A dataset whose golden file records legacy behaviour repaired by an approved source-representation correction
    is registered in APPROVED_SOURCE_CORRECTIONS, and only then, with the evidence ``approved_source_correction_problems``
    requires. Every golden file named is also pinned to the legacy commit (``load_cases``)."""
    evidence = approved_source_correction_evidence()
    assert approved_source_correction_problems(**evidence) == []
    for code, registered in APPROVED_SOURCE_CORRECTIONS.items():
        load_cases(OBSERVATION_CASES.get(code) or registered.golden)


def _mutated(**changes):
    import copy

    evidence = copy.deepcopy(approved_source_correction_evidence())
    for key, change in changes.items():
        evidence[key] = change(evidence[key])
    return approved_source_correction_problems(**evidence)


def _with(mapping, key, value):
    return {**mapping, key: value}


def test_the_gate_refuses_an_unconfirmed_or_unrecorded_approval():
    import dataclasses

    assert "SIPRI_ARMEXP: approval not confirmed" in _mutated(register=lambda r: _with(r, "SIPRI_ARMEXP", dataclasses.replace(r["SIPRI_ARMEXP"], confirmed=False)))
    assert any("golden name table differs" in p for p in _mutated(register=lambda r: _with(r, "SIPRI_ARMEXP", dataclasses.replace(r["SIPRI_ARMEXP"], name_corrections={**r["SIPRI_ARMEXP"].name_corrections, "Narnia": "NAR"}))))
    assert any(p.startswith("golden files with approved corrections") for p in _mutated(register=lambda r: {k: v for k, v in r.items() if k != "SIPRI_ARMEXP"}))  # an unregistered correction
    assert any("must be resolved and record the approval" in p for p in _mutated(documented=lambda d: _with(d, "ARMEXP-4", d["ARMEXP-4"].replace("Status: resolved", "Status: unresolved"))))


def test_the_gate_refuses_a_correction_without_legacy_evidence():
    golden = OBSERVATION_CASES["SIPRI_ARMEXP"]

    def strip(goldens):
        case = dict(goldens[golden])
        case["legacy_dropped_rows"], case["invalid_variants"], case["legacy_clean_error"] = [], {}, None
        return _with(goldens, golden, case)

    assert "SIPRI_ARMEXP: no recorded legacy behaviour" in _mutated(goldens=strip)

    def foreign_rows(goldens):
        case = dict(goldens[golden])
        case["legacy_dropped_rows"] = [*case["legacy_dropped_rows"], {"country_code": "AUT", "year": 2000, "value": 1.0, "unit": "x"}]
        return _with(goldens, golden, case)

    assert "SIPRI_ARMEXP: dropped rows of a country the name table does not repair" in _mutated(goldens=foreign_rows)
    milex = APPROVED_SOURCE_CORRECTIONS["SIPRI_MILEXP"].golden

    def wrong_divergence(goldens):
        case = dict(goldens[milex])
        case["legacy_divergence"] = {**case["legacy_divergence"], "names": {n: {**v, "legacy_code": v["approved"]} for n, v in case["legacy_divergence"]["names"].items()}}
        return _with(goldens, milex, case)

    assert "SIPRI_MILEXP: the recorded legacy divergence does not cover exactly the corrected names" in _mutated(goldens=wrong_divergence)


def test_a_blocked_dataset_cannot_become_ingestible_or_lose_its_block():
    assert any("blocked by MILEXP-5, so neither ingestible" in p for p in _mutated(supported=lambda s: s | {"SIPRI_MILEXP"}))
    assert any("blocked by MILEXP-5, so neither ingestible" in p for p in _mutated(readers=lambda r: _with(r, "SIPRI_MILEXP", ["MILEXP"])))
    assert any("MILEXP-5 must stay unresolved" in p for p in _mutated(documented=lambda d: _with(d, "MILEXP-5", d["MILEXP-5"].replace("Status: unresolved", "Status: resolved"))))
    assert any("approved and unblocked, but not ingestible" in p for p in _mutated(supported=lambda s: s - {"SIPRI_ARMEXP"}))


def test_unrelated_datasets_are_unaffected_by_the_extension():
    """The earlier corrections still rest on a recorded legacy clean failure, and a dataset without an approved table
    gains nothing from dropped rows or a divergence record."""
    goldens = approved_source_correction_evidence()["goldens"]
    for code in ("ITU_CYBSEC", "FSI_SECAPP"):
        case = goldens[OBSERVATION_CASES[code]]
        assert "legacy_dropped_rows" not in case and "legacy_divergence" not in case
        assert any((v if isinstance(v, str) else v.get("legacy_error") or "").startswith("InvalidDocumentFormatError") for v in [case.get("legacy_clean_error"), *case.get("invalid_variants", {}).values()] if v)
    unrelated = OBSERVATION_CASES["WB_MURDER"]

    def smuggled(goldens):
        return _with(goldens, unrelated, {**goldens[unrelated], "approved_name_corrections": {"Narnia": "NAR"}, "legacy_dropped_rows": []})

    assert any(p.startswith("golden files with approved corrections") for p in _mutated(goldens=smuggled))


def test_proposed_source_corrections_stay_unconfirmed_and_unregistered():
    """A proposed correction is never confirmed, its dataset is not ingestible, its golden file records exactly the
    proposed name table, its cited entry is not resolved, and the migration doc lists it as proposed."""
    documented = entries()
    section = MIGRATION.split("## Proposed source-representation corrections", 1)[1].split("\n## ", 1)[0]
    assert not set(PROPOSED_SOURCE_CORRECTIONS) & set(APPROVED_SOURCE_CORRECTIONS)
    for code, proposed in PROPOSED_SOURCE_CORRECTIONS.items():
        assert proposed.confirmed is False and proposed.status, code
        assert code not in SUPPORTED_DATASETS and code not in OBSERVATION_CASES, f"{code}: a dataset with an unconfirmed correction must not be ingestible"
        case = load_cases(proposed.golden)
        assert case["dataset_code"] == code and case["proposed_name_corrections"] == proposed.name_corrections, f"{code}: golden name table differs from the register"
        assert case["observations"], code
        assert proposed.conflict in documented, f"{code}: cites {proposed.conflict}, which is not in docs/methodology-conflicts.md"
        text = documented[proposed.conflict]
        assert "Status: resolved" not in text and "Proposed source-representation correction" in text, f"{proposed.conflict}: must stay open and describe the proposal"
        assert f"`{code}`" in section and proposed.conflict in section, f"{code}: must be listed under 'Proposed source-representation corrections' in docs/indicator-migration.md"


def registry_row_imputes(code: str) -> str:
    return register_row(code)[3]


def test_conflict_entries_are_well_formed():
    found = entries()
    assert found, "no entries parsed from docs/methodology-conflicts.md"
    for identifier, text in found.items():
        status = re.findall(r"^Status: (.+)$", text, re.MULTILINE)
        assert len(status) == 1 and status[0] in STATUSES, f"{identifier}: Status must be one of {sorted(STATUSES)}, got {status}"
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{identifier}: missing section {section!r}"
        index = re.search(rf"^\| {re.escape(identifier)} \| .+ \| (\w+) \|$", CONFLICTS, re.MULTILINE)
        assert index and index.group(1) == status[0], f"{identifier}: index table row missing or its status differs from the entry"


def test_conflict_entries_cite_files_that_exist():
    cited = set(re.findall(r"`((?:src|tests|docs|scripts)/[^`\s(]+)`", CONFLICTS))
    assert cited and not [p for p in cited if not (REPO_ROOT / p).exists()]


def test_nothing_is_marked_resolved_without_cited_evidence():
    for identifier, text in entries().items():
        if "Status: resolved" in text:
            assert "Resolution evidence:" in text, f"{identifier}: resolved entries must carry a 'Resolution evidence:' section"
