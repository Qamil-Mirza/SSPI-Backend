"""One-time, reproducible import of the legacy SSPI metadata into canonical YAML.

Reads the Markdown-with-YAML-frontmatter files of the old repository
(``methodology/**/methodology.md`` and ``datasets/**/documentation.md``) and
``local/country-groups.json``, applies the documented transformations, and
writes:

    src/sspi/metadata/data/indicators/<CODE>.yaml
    src/sspi/metadata/data/datasets/<CODE>.yaml
    src/sspi/metadata/data/country_groups.yaml
    src/sspi/metadata/data/PROVENANCE.yaml

The approved corrections to the legacy values (``edits``) and the datasets
imported although no indicator references them (``additions``) are read from
the checked-in ``PROVENANCE.yaml``, which is their only record: approve a
correction by adding it there, then re-run this script. Both sections are
written back as read.

Dev-only. Never imported by the ``sspi`` package. Re-running it regenerates the
files from scratch and, at the same legacy commit, reproduces the checked-in
files byte for byte (``tests/golden/test_metadata_importer.py``).

    .venv/bin/python scripts/import_legacy_metadata.py [--old-repo PATH] [--output-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "src" / "sspi" / "metadata" / "data"

PROVENANCE_FILE = "PROVENANCE.yaml"
EDIT_KEYS = {"file", "field", "old", "new", "reason"}
ADDITION_KEYS = {"file", "source", "reason"}


def load_approved_corrections(path: Path) -> tuple[list[dict], list[dict]]:
    """(edits, additions) from the checked-in PROVENANCE.yaml, in file order.

    PROVENANCE.yaml is the only list of approved corrections; nothing in this
    script repeats it. ``edits`` change one field of one legacy record.
    ``additions`` import a legacy dataset no indicator's DatasetCodes
    references, with the given ``source`` fields set on top of the converted
    legacy record. Both sections are written back unchanged.
    """
    if not path.is_file():
        raise SystemExit(f"{path} not found: it holds the approved edits and additions and cannot be regenerated without them")
    provenance = yaml.safe_load(path.read_text(encoding="utf-8"))
    edits, additions = provenance.get("edits"), provenance.get("additions")
    if not isinstance(edits, list) or not isinstance(additions, list):
        raise SystemExit(f"{path}: 'edits' and 'additions' must both be lists")
    for name, entries, keys in (("edits", edits, EDIT_KEYS), ("additions", additions, ADDITION_KEYS)):
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != keys:
                raise SystemExit(f"{path}: every entry of '{name}' needs exactly the keys {sorted(keys)}; found {entry!r}")
    return edits, additions


TRANSFORMATIONS = [
    "Markdown frontmatter converted to plain YAML, one file per code; prose bodies not migrated.",
    "Legacy PascalCase keys renamed to snake_case model fields "
    "(ItemCode->code, ItemName->name, DatasetCodes->dataset_codes, LowerGoalpost->lower_goalpost, "
    "UpperGoalpost->upper_goalpost, ScoreFunction->score_function, Policy->policy, Footnote->footnote, "
    "Description->description, DatasetCode->code, DatasetName->name, DatasetType->dataset_type, Unit->unit, "
    "Source.OrganizationCode->source.organization_code, Source.QueryCode->source.query_code, "
    "Source.OrganizationSeriesCode->source.organization_series_code, Source.OrganizationName->source.organization_name, "
    "Source.BaseURL->source.base_url, Source.Format->source.format, Source.Note->source.note).",
    "pillar_code and category_code written explicitly from the legacy methodology directory position "
    "(methodology/<pillar>/<category>/<indicator>/).",
    "Keys dropped: ItemType (implied by directory), Indicator and IndicatorCode (duplicates of name/code), "
    "DatasetProcessorFile (path into the legacy repository; wrong for at least 10 datasets).",
    "Goalposts written as floats; numeric values unchanged.",
    "Trailing whitespace stripped from multi-line strings (description, score_function).",
    "Only datasets referenced by an indicator's DatasetCodes were migrated; referenced codes with no legacy "
    "definition were written as explicit unresolved entries.",
    "Country groups copied verbatim from local/country-groups.json into one country_groups.yaml: "
    "same group order, same member order, same memberships (SSPI67 keeps its 66 members). "
    "Legacy key CountryGroupName->code, Countries->members. No names, flags or attributes added; "
    "country names are derived from pycountry at load time exactly as the legacy loader did.",
    "Pillar, category and SSPI-root definitions, organizations and time periods were not migrated in this step.",
]

FRONTMATTER_BOUNDARY = re.compile(r"^-{3,}\s*$", re.MULTILINE)


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_BOUNDARY.match(text)
    if not match:
        raise ValueError(f"{path}: no frontmatter")
    end = FRONTMATTER_BOUNDARY.search(text, match.end())
    if not end:
        raise ValueError(f"{path}: unterminated frontmatter")
    data = yaml.safe_load(text[match.end():end.start()])
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return data


def clean_text(value):
    return value.rstrip() if isinstance(value, str) else value


def git(old_repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(old_repo), *args], text=True).strip()


def load_indicators(old_repo: Path, notes: list[str]) -> dict[str, dict]:
    indicators: dict[str, dict] = {}
    root = old_repo / "methodology"
    for md in sorted(root.rglob("methodology.md")):
        meta = read_frontmatter(md)
        if meta.get("ItemType") != "Indicator":
            continue
        rel = md.parent.relative_to(root).parts  # (pillar, category, indicator)
        if len(rel) != 3:
            raise ValueError(f"{md}: indicator not at depth 3 under methodology/")
        code = meta["ItemCode"]
        name = meta["ItemName"]
        if meta.get("Indicator") not in (None, name):
            notes.append(f"{code}: ItemName {name!r} != Indicator {meta['Indicator']!r}")
        if meta.get("IndicatorCode") not in (None, code):
            raise ValueError(f"{md}: IndicatorCode {meta['IndicatorCode']!r} != ItemCode {code!r}")
        indicators[code] = {
            "code": code,
            "name": name,
            "pillar_code": rel[0].upper(),
            "category_code": rel[1].upper(),
            "policy": clean_text(meta.get("Policy")),
            "description": clean_text(meta.get("Description")),
            "footnote": clean_text(meta.get("Footnote")),
            "dataset_codes": list(meta["DatasetCodes"]),
            "lower_goalpost": None if meta.get("LowerGoalpost") is None else float(meta["LowerGoalpost"]),
            "upper_goalpost": None if meta.get("UpperGoalpost") is None else float(meta["UpperGoalpost"]),
            "score_function": clean_text(meta.get("ScoreFunction")),
        }
    return indicators


def load_legacy_datasets(old_repo: Path) -> dict[str, dict]:
    datasets: dict[str, dict] = {}
    for md in sorted((old_repo / "datasets").rglob("documentation.md")):
        meta = read_frontmatter(md)
        code = meta["DatasetCode"]
        if code in datasets:
            raise ValueError(f"duplicate legacy DatasetCode {code}")
        datasets[code] = meta
    return datasets


def load_country_groups(old_repo: Path) -> dict:
    """Legacy group dict -> canonical record, order and members untouched."""
    with (old_repo / "local" / "country-groups.json").open(encoding="utf-8") as fh:
        legacy = json.load(fh)
    if not isinstance(legacy, dict) or not legacy:
        raise ValueError("local/country-groups.json is not a non-empty mapping")
    groups = []
    for name, members in legacy.items():
        if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
            raise ValueError(f"country group {name!r} is not a list of strings")
        groups.append({"code": name, "members": list(members)})
    return {"groups": groups}


SOURCE_KEY_MAP = {
    "OrganizationCode": "organization_code",
    "OrganizationSeriesCode": "organization_series_code",
    "QueryCode": "query_code",
    "OrganizationName": "organization_name",
    "BaseURL": "base_url",
    "Format": "format",
    "Note": "note",
}


def convert_dataset(meta: dict) -> dict:
    legacy_source = meta["Source"]
    unknown = set(legacy_source) - set(SOURCE_KEY_MAP)
    if unknown:
        raise ValueError(f"{meta['DatasetCode']}: unknown Source keys {sorted(unknown)}")
    source = {
        "organization_code": legacy_source.get("OrganizationCode"),
        "organization_series_code": legacy_source.get("OrganizationSeriesCode"),
        "query_code": legacy_source.get("QueryCode"),
    }
    for legacy_key in ("OrganizationName", "BaseURL", "Format", "Note"):
        if legacy_key in legacy_source:
            source[SOURCE_KEY_MAP[legacy_key]] = legacy_source[legacy_key]
    return {
        "code": meta["DatasetCode"],
        "status": "documented",
        "name": meta["DatasetName"],
        "dataset_type": meta["DatasetType"],
        "description": clean_text(meta.get("Description")),
        "unit": meta.get("Unit"),
        "source": source,
    }


def unresolved_entry(code: str, referenced_by: list[str], commit: str) -> dict:
    return {
        "code": code,
        "status": "unresolved",
        "note": (
            f"Referenced by indicator(s) {', '.join(referenced_by)} in the legacy methodology, but no "
            f"dataset definition existed in sspi-data-webapp at commit {commit[:8]}. Name, source and "
            "unit are unknown."
        ),
    }


def apply_edits(edits: list[dict], indicators: dict[str, dict], datasets: dict[str, dict]) -> None:
    for edit in edits:
        kind, filename = edit["file"].split("/")
        code = filename.removesuffix(".yaml")
        record = indicators[code] if kind == "indicators" else datasets[code]
        target = record
        *parents, leaf = edit["field"].split(".")
        for key in parents:
            target = target[key]
        current = target.get(leaf)
        expected_old = edit["old"] if not isinstance(edit["old"], dict) else edit["old"]["ItemName"]
        if current != expected_old:
            raise ValueError(f"edit {edit['file']} {edit['field']}: expected legacy value {expected_old!r}, found {current!r}")
        target[leaf] = edit["new"]


def apply_additions(additions: list[dict], datasets: dict[str, dict], legacy_datasets: dict[str, dict]) -> None:
    for addition in additions:
        code = addition["file"].split("/")[1].removesuffix(".yaml")
        if code in datasets:
            raise ValueError(f"addition {code} is already imported")
        record = convert_dataset(legacy_datasets[code])
        record["source"].update(addition["source"])
        datasets[code] = record


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def dump_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")


def count_implemented(old_repo: Path) -> set[str]:
    codes: set[str] = set()
    for py in (old_repo / "sspi_flask_app" / "api" / "core" / "datasets").rglob("*.py"):
        codes |= set(re.findall(r'@dataset_cleaner\("([A-Z0-9_]+)"\)', py.read_text(encoding="utf-8")))
    return codes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-repo", type=Path, default=REPO_ROOT.parent / "sspi-data-webapp")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR, help="write here instead of the canonical metadata directory")
    args = parser.parse_args()
    old_repo = args.old_repo.resolve()
    output_dir = args.output_dir.resolve()
    edits, additions = load_approved_corrections(DATA_DIR / PROVENANCE_FILE)
    previous = yaml.safe_load((DATA_DIR / PROVENANCE_FILE).read_text(encoding="utf-8"))

    commit = git(old_repo, "rev-parse", "HEAD")
    dirty = bool(git(old_repo, "status", "--porcelain"))
    notes: list[str] = []

    indicators = load_indicators(old_repo, notes)
    legacy_datasets = load_legacy_datasets(old_repo)
    referenced_by: dict[str, list[str]] = {}
    for code, ind in indicators.items():
        for ds in ind["dataset_codes"]:
            referenced_by.setdefault(ds, []).append(code)

    datasets: dict[str, dict] = {}
    unresolved: list[dict] = []
    for ds_code in sorted(referenced_by):
        if ds_code in legacy_datasets:
            datasets[ds_code] = convert_dataset(legacy_datasets[ds_code])
        else:
            datasets[ds_code] = unresolved_entry(ds_code, referenced_by[ds_code], commit)
            unresolved.append({"code": ds_code, "referenced_by": referenced_by[ds_code], "reason": "no legacy definition"})

    apply_edits(edits, indicators, datasets)
    apply_additions(additions, datasets, legacy_datasets)

    for sub in ("indicators", "datasets"):
        target = output_dir / sub
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob("*.yaml"):
            stale.unlink()
    for code, record in indicators.items():
        dump_yaml(output_dir / "indicators" / f"{code}.yaml", record)
    for code, record in datasets.items():
        dump_yaml(output_dir / "datasets" / f"{code}.yaml", record)
    country_groups = load_country_groups(old_repo)
    dump_yaml(output_dir / "country_groups.yaml", country_groups)

    implemented = count_implemented(old_repo)
    documented = set(legacy_datasets)
    referenced = set(referenced_by)
    documented_count = sum(1 for d in datasets.values() if d["status"] == "documented")
    provenance = {
        "source_repository": "sspi-data-webapp",
        "source_commit": commit,
        "source_working_tree_dirty": dirty,
        # The date this legacy commit was imported; regenerating from the same commit does not change it.
        "imported_at": previous["imported_at"] if previous.get("source_commit") == commit else date.today().isoformat(),
        "importer": "scripts/import_legacy_metadata.py",
        "counts": {
            "indicators": len(indicators),
            "datasets_documented": documented_count,
            "datasets_unresolved": len(unresolved),
            "country_groups": len(country_groups["groups"]),
            "country_codes_in_any_group": len({m for g in country_groups["groups"] for m in g["members"]}),
        },
        "transformations": TRANSFORMATIONS,
        "edits": edits,
        "unresolved_datasets": unresolved,
        "additions": additions,
        "legacy_conflicts_observed": notes,
        "not_migrated": {
            "legacy_dataset_definitions_total": len(documented),
            "dataset_definitions_with_collector_but_no_indicator_reference": len((documented & implemented) - referenced),
            "dataset_definitions_without_collector_or_indicator_reference": len(documented - implemented - referenced),
            "methodology_prose_bodies": "deferred",
            "pillar_category_and_root_definitions": "deferred to the hierarchy step",
            "local_json_and_csv_files": "deferred (organizations, time periods, globe geojson) or legacy-only",
        },
    }
    dump_yaml(output_dir / PROVENANCE_FILE, provenance)
    print(
        f"wrote {len(indicators)} indicators, {documented_count} documented + {len(unresolved)} unresolved datasets, "
        f"{len(country_groups['groups'])} country groups from {commit}{' (dirty)' if dirty else ''}; notes: {notes}"
    )


if __name__ == "__main__":
    main()
