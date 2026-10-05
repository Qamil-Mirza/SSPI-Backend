"""One-time, reproducible import of the legacy SSPI metadata into canonical YAML.

Reads the Markdown-with-YAML-frontmatter files of the old repository
(``methodology/**/methodology.md`` and ``datasets/**/documentation.md``) and
``local/country-groups.json``, applies the documented transformations, and
writes:

    src/sspi/metadata/data/indicators/<CODE>.yaml
    src/sspi/metadata/data/datasets/<CODE>.yaml
    src/sspi/metadata/data/country_groups.yaml
    src/sspi/metadata/data/PROVENANCE.yaml

Dev-only. Never imported by the ``sspi`` package. Re-running it regenerates the
files from scratch.

    .venv/bin/python scripts/import_legacy_metadata.py [--old-repo PATH]
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

# Edits applied to the legacy values. Each one is recorded verbatim in PROVENANCE.yaml.
EDITS = [
    {
        "file": "datasets/WB_PUPTCH.yaml",
        "field": "source.organization_code",
        "old": None,
        "new": "WB",
        "reason": (
            "Legacy Source block had only OrganizationName 'World Bank' and QueryCode; "
            "the WB_ prefix and the organization name make the code unambiguous."
        ),
    },
    {
        "file": "indicators/FDEPTH.yaml",
        "field": "name",
        "old": {"ItemName": "Financial Depth", "Indicator": "Depth"},
        "new": "Financial Depth",
        "reason": (
            "Legacy frontmatter carried two conflicting names. ItemName was the key the "
            "legacy loader treated as canonical; Indicator was a display alias."
        ),
    },
    {
        "file": "datasets/UNSDG_MARINE.yaml",
        "field": "source.organization_series_code",
        "old": "14.5.1",
        "new": "ER_MRN_MPA",
        "reason": (
            "Legacy metadata repeated the SDG indicator code here. The series the legacy cleaner "
            "actually selects (idcode_map in api/core/datasets/unsdg/unsdg_marine.py) is ER_MRN_MPA; "
            "query_code stays 14.5.1, the SDG indicator requested from the UN API."
        ),
    },
    {
        "file": "datasets/UNSDG_TERRST.yaml",
        "field": "source.organization_series_code",
        "old": "15.1.2",
        "new": "ER_PTD_TERR",
        "reason": (
            "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects "
            "(idcode_map in api/core/datasets/unsdg/unsdg_terrst.py) is ER_PTD_TERR; query_code stays 15.1.2."
        ),
    },
    {
        "file": "datasets/UNSDG_FRSHWT.yaml",
        "field": "source.organization_series_code",
        "old": "15.1.2",
        "new": "ER_PTD_FRHWTR",
        "reason": (
            "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects "
            "(idcode_map in api/core/datasets/unsdg/unsdg_frshwt.py) is ER_PTD_FRHWTR; query_code stays 15.1.2."
        ),
    },
    {
        "file": "datasets/UNSDG_REDLST.yaml",
        "field": "source.organization_series_code",
        "old": "15.5.1",
        "new": "ER_RSK_LST",
        "reason": (
            "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects "
            "(idcode_map in api/core/datasets/unsdg/unsdg_redlst.py) is ER_RSK_LST, the only series in the "
            "15.5.1 response; query_code stays 15.5.1. Corrected 2026-09-29 for the REDLST port."
        ),
    },
    {"file": "datasets/UNSDG_STKHLM.yaml", "field": "source.organization_series_code", "old": "12.4.1", "new": "SG_HAZ_CMRSTHOLM",
     "reason": "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects (idcode_map in api/core/datasets/unsdg/unsdg_stkhlm.py) is SG_HAZ_CMRSTHOLM; query_code stays 12.4.1. Corrected 2026-10-01 for the CHMPOL port."},
    {"file": "datasets/UNSDG_MINMAT.yaml", "field": "source.organization_series_code", "old": "12.4.1", "new": "SG_HAZ_CMRMNMT",
     "reason": "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects (unsdg_minmat.py) is SG_HAZ_CMRMNMT; query_code stays 12.4.1. Corrected 2026-10-01 for the CHMPOL port."},
    {"file": "datasets/UNSDG_MONTRL.yaml", "field": "source.organization_series_code", "old": "12.4.1", "new": "SG_HAZ_CMRMNTRL",
     "reason": "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects (unsdg_montrl.py) is SG_HAZ_CMRMNTRL; query_code stays 12.4.1. Corrected 2026-10-01 for the CHMPOL port."},
    {"file": "datasets/UNSDG_BASELA.yaml", "field": "source.organization_series_code", "old": "12.4.1", "new": "SG_HAZ_CMRBASEL",
     "reason": "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner selects (unsdg_basela.py) is SG_HAZ_CMRBASEL; query_code stays 12.4.1. Corrected 2026-10-01 for the CHMPOL port."},
    {"file": "datasets/UNSDG_ROTDAM.yaml", "field": "source.organization_series_code", "old": "12.4.1", "new": "SG_HAZ_CMRSTHOLM",
     "reason": "Legacy metadata repeated the SDG indicator code. The series the legacy cleaner actually selects (unsdg_rotdam.py) is SG_HAZ_CMRSTHOLM, the Stockholm series, although the source publishes SG_HAZ_CMRROTDAM. The executable behaviour is reproduced on purpose; the methodology question is CHMPOL-1 in docs/methodology-conflicts.md. Recorded 2026-10-01."},
    {"file": "datasets/UNSDG_WTSTRS.yaml", "field": "source.organization_series_code", "old": None, "new": "ER_H2O_STRESS",
     "reason": "Legacy metadata had no series code. The legacy cleaner (unsdg_wtstrs.py) selects ER_H2O_STRESS with activity=TOTAL. Corrected 2026-10-01 for the WATMAN port."},
    {"file": "datasets/UNSDG_WTSTRS.yaml", "field": "source.dimensions", "old": None, "new": {"activity": "TOTAL"},
     "reason": 'The legacy cleaner passes activity="TOTAL" to filter_sdg; the source publishes four activity slices per area. Recorded 2026-10-01.'},
    {"file": "datasets/UNSDG_CWUEFF.yaml", "field": "source.organization_series_code", "old": None, "new": "ER_H2O_WUEYST",
     "reason": "Legacy metadata had no series code. The legacy cleaner (unsdg_cwueff.py) selects ER_H2O_WUEYST with activity=TOTAL and then derives the baseline change. Corrected 2026-10-01 for the WATMAN port."},
    {"file": "datasets/UNSDG_CWUEFF.yaml", "field": "source.dimensions", "old": None, "new": {"activity": "TOTAL"},
     "reason": 'The legacy cleaner passes activity="TOTAL" to filter_sdg. Recorded 2026-10-01.'},
    {"file": "datasets/UNSDG_ROTDAM.yaml", "field": "source.note", "old": None, "new": 'Reproduces the legacy cleaner, which selects the Stockholm series for this dataset although the source publishes SG_HAZ_CMRROTDAM. See CHMPOL-1 in docs/methodology-conflicts.md.',
     "reason": "Flag the deliberate legacy series mapping in the canonical file itself. Recorded 2026-10-01."},
    {"file": "datasets/UNSDG_CWUEFF.yaml", "field": "source.note", "old": None, "new": 'Derived dataset. The ER_H2O_WUEYST observations are normalized as UNSDG_WUSEFF, then sspi.ingestion.derived applies the legacy transform; percent change from the 2000-2005 mean, years from 2006.',
     "reason": "Flag that this dataset is derived in Python from UNSDG_WUSEFF rather than selected directly from the source. Recorded 2026-10-01."},
    {"file": 'datasets/WID_NINCSH_PRETAX_P0P50.yaml', "field": 'source.organization_series_code', "old": None, "new": 'sptincj992',
     "reason": 'Legacy metadata had no series code. The legacy cleaner (wid_nincsh_pretax_p0p50.py) selects WID variable sptincj992 (share of pre-tax national income, equal-split adults, age 20+); query_code stays wid_all_data, the bulk archive. Corrected 2026-10-05 for the ISHRAT port.'},
    {"file": 'datasets/WID_NINCSH_PRETAX_P0P50.yaml', "field": 'source.dimensions', "old": None, "new": {'percentile': 'p0p50'},
     "reason": 'The legacy cleaner passes percentile "p0p50" to filter_wid_csv; the source publishes about 130 percentile groups per variable. Recorded 2026-10-05.'},
    {"file": 'datasets/WID_NINCSH_PRETAX_P0P50.yaml', "field": 'source.note', "old": None, "new": "Values reproduce the legacy numeric representation: the cleaner read the WID value column as float32 and serialized it with ten decimals, so a published 0.1921 is stored as 0.1921000034. The published text is kept in each observation's provenance (source_value). Countries are the SSPI67 members and years 2000-2024, as in every legacy WID cleaner.",
     "reason": 'Known source-representation quirk, preserved on purpose for exact legacy parity (decision of 2026-10-05); not a methodology change and not a correction of WID values. Recorded 2026-10-05.'},
    {"file": 'datasets/WID_NINCSH_PRETAX_P90P100.yaml', "field": 'source.organization_series_code', "old": None, "new": 'sptincj992',
     "reason": 'Legacy metadata had no series code. The legacy cleaner (wid_nincsh_pretax_p90p100.py) selects WID variable sptincj992 (share of pre-tax national income, equal-split adults, age 20+); query_code stays wid_all_data, the bulk archive. Corrected 2026-10-05 for the ISHRAT port.'},
    {"file": 'datasets/WID_NINCSH_PRETAX_P90P100.yaml', "field": 'source.dimensions', "old": None, "new": {'percentile': 'p90p100'},
     "reason": 'The legacy cleaner passes percentile "p90p100" to filter_wid_csv; the source publishes about 130 percentile groups per variable. Recorded 2026-10-05.'},
    {"file": 'datasets/WID_NINCSH_PRETAX_P90P100.yaml', "field": 'source.note', "old": None, "new": "Values reproduce the legacy numeric representation: the cleaner read the WID value column as float32 and serialized it with ten decimals, so a published 0.1921 is stored as 0.1921000034. The published text is kept in each observation's provenance (source_value). Countries are the SSPI67 members and years 2000-2024, as in every legacy WID cleaner.",
     "reason": 'Known source-representation quirk, preserved on purpose for exact legacy parity (decision of 2026-10-05); not a methodology change and not a correction of WID values. Recorded 2026-10-05.'},
]

# Datasets with a legacy definition and collector that no indicator's DatasetCodes references, but
# that legacy indicator code reads. Imported in addition to the referenced ones.
ADDITIONS = [
    {
        "file": "datasets/UNSDG_WUSEFF.yaml",
        "source": {"organization_series_code": "ER_H2O_WUEYST", "dimensions": {"activity": "TOTAL"}},
        "reason": (
            "Not referenced by any indicator's DatasetCodes, so not migrated by the first import, but a "
            "genuine legacy input: the WATMAN impute route reads UNSDG_WUSEFF to build synthetic UNSDG_CWUEFF "
            "series. Converted from datasets/unsdg/unsdg_wuseff/documentation.md with series ER_H2O_WUEYST and "
            "activity=TOTAL from unsdg_wuseff.py. Added 2026-10-01."
        ),
    },
]

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


def apply_edits(indicators: dict[str, dict], datasets: dict[str, dict]) -> None:
    for edit in EDITS:
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


def apply_additions(datasets: dict[str, dict], legacy_datasets: dict[str, dict]) -> None:
    for addition in ADDITIONS:
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
    args = parser.parse_args()
    old_repo = args.old_repo.resolve()

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

    apply_edits(indicators, datasets)
    apply_additions(datasets, legacy_datasets)

    for sub in ("indicators", "datasets"):
        target = DATA_DIR / sub
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob("*.yaml"):
            stale.unlink()
    for code, record in indicators.items():
        dump_yaml(DATA_DIR / "indicators" / f"{code}.yaml", record)
    for code, record in datasets.items():
        dump_yaml(DATA_DIR / "datasets" / f"{code}.yaml", record)
    country_groups = load_country_groups(old_repo)
    dump_yaml(DATA_DIR / "country_groups.yaml", country_groups)

    implemented = count_implemented(old_repo)
    documented = set(legacy_datasets)
    referenced = set(referenced_by)
    documented_count = sum(1 for d in datasets.values() if d["status"] == "documented")
    provenance = {
        "source_repository": "sspi-data-webapp",
        "source_commit": commit,
        "source_working_tree_dirty": dirty,
        "imported_at": date.today().isoformat(),
        "importer": "scripts/import_legacy_metadata.py",
        "counts": {
            "indicators": len(indicators),
            "datasets_documented": documented_count,
            "datasets_unresolved": len(unresolved),
            "country_groups": len(country_groups["groups"]),
            "country_codes_in_any_group": len({m for g in country_groups["groups"] for m in g["members"]}),
        },
        "transformations": TRANSFORMATIONS,
        "edits": EDITS,
        "unresolved_datasets": unresolved,
        "additions": [{"file": a["file"], "reason": a["reason"]} for a in ADDITIONS],
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
    dump_yaml(DATA_DIR / "PROVENANCE.yaml", provenance)
    print(
        f"wrote {len(indicators)} indicators, {documented_count} documented + {len(unresolved)} unresolved datasets, "
        f"{len(country_groups['groups'])} country groups from {commit}{' (dirty)' if dirty else ''}; notes: {notes}"
    )


if __name__ == "__main__":
    main()
