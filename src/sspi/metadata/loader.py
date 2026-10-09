"""Read and validate the canonical metadata YAML files.

Layout expected under ``root``::

    indicators/<CODE>.yaml   one IndicatorMetadata each
    datasets/<CODE>.yaml     one DatasetMetadata (status: documented)
                             or UnresolvedDataset (status: unresolved) each

Codes come from the ``code`` field, not the file name, so duplicate codes are
detected rather than made impossible by construction. Every problem found in
the tree is collected and raised together in one ``MetadataError``.

Nothing in this module runs at import time; ``load_catalog_data`` is the only
entry point that touches the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sspi.errors import MetadataError
from sspi.metadata.models import DatasetMetadata, IndicatorMetadata, SourceMetadata, UnresolvedDataset

INDICATOR_KEYS = frozenset(
    {
        "code",
        "name",
        "pillar_code",
        "category_code",
        "policy",
        "description",
        "footnote",
        "dataset_codes",
        "lower_goalpost",
        "upper_goalpost",
        "score_function",
    }
)
INDICATOR_REQUIRED_TEXT = ("code", "name", "pillar_code", "category_code", "description")
INDICATOR_OPTIONAL_TEXT = ("policy", "footnote", "score_function")

DATASET_KEYS = frozenset({"code", "status", "name", "dataset_type", "description", "unit", "source"})
SOURCE_KEYS = frozenset(
    {"organization_code", "query_code", "organization_series_code", "dimensions", "organization_name", "base_url", "format", "note", "published_unit", "value_multiplier"}
)
UNRESOLVED_KEYS = frozenset({"code", "status", "note"})
STATUSES = ("documented", "unresolved")


@dataclass(frozen=True, slots=True)
class CatalogData:
    """Validated records, ready to be wrapped by ``MetadataCatalog``."""

    indicators: dict[str, IndicatorMetadata]
    datasets: dict[str, DatasetMetadata | UnresolvedDataset]


def read_yaml(path: Path) -> Any:
    """Parse one YAML file. Patched by tests to prove queries never re-read."""
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class _Problems:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.items: list[str] = []

    def where(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def add(self, path: Path, message: str) -> None:
        self.items.append(f"{self.where(path)}: {message}")

    def raise_if_any(self) -> None:
        if self.items:
            lines = [f"metadata validation failed with {len(self.items)} problem(s):"]
            lines += [f"  - {item}" for item in self.items]
            raise MetadataError("\n".join(lines))


# --------------------------------------------------------------------------- #
# Field checks
# --------------------------------------------------------------------------- #


def _check_keys(record: dict, allowed: frozenset[str], path: Path, problems: _Problems, context: str = "") -> None:
    for key in sorted(set(record) - allowed):
        problems.add(path, f"unknown key {context}{key!r}")


def _text(record: dict, key: str, path: Path, problems: _Problems, *, required: bool, context: str = "") -> str | None:
    if key not in record:
        if required:
            problems.add(path, f"missing required field {context}{key!r}")
        return None
    value = record[key]
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value):
        expectation = "a non-empty string" if required else "a string or null"
        problems.add(path, f"field {context}{key!r} must be {expectation}, got {value!r}")
        return None
    return value


def _number_or_null(record: dict, key: str, path: Path, problems: _Problems) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.add(path, f"field {key!r} must be a number or null, got {value!r}")
        return None
    return float(value)


def _dataset_codes(record: dict, path: Path, problems: _Problems) -> tuple[str, ...]:
    value = record.get("dataset_codes")
    if not isinstance(value, list) or not value:
        problems.add(path, f"field 'dataset_codes' must be a non-empty list, got {value!r}")
        return ()
    if any(not isinstance(v, str) or not v for v in value):
        problems.add(path, f"field 'dataset_codes' entries must be non-empty strings, got {value!r}")
        return ()
    if len(set(value)) != len(value):
        problems.add(path, f"field 'dataset_codes' contains duplicates: {value!r}")
        return ()
    return tuple(value)


# --------------------------------------------------------------------------- #
# Record parsers
# --------------------------------------------------------------------------- #


def parse_indicator(path: Path, record: dict, problems: _Problems) -> IndicatorMetadata | None:
    before = len(problems.items)
    _check_keys(record, INDICATOR_KEYS, path, problems)
    text = {key: _text(record, key, path, problems, required=True) for key in INDICATOR_REQUIRED_TEXT}
    optional = {key: _text(record, key, path, problems, required=False) for key in INDICATOR_OPTIONAL_TEXT}
    dataset_codes = _dataset_codes(record, path, problems)
    lower = _number_or_null(record, "lower_goalpost", path, problems)
    upper = _number_or_null(record, "upper_goalpost", path, problems)
    if len(problems.items) != before:
        return None
    return IndicatorMetadata(
        code=text["code"],
        name=text["name"],
        pillar_code=text["pillar_code"],
        category_code=text["category_code"],
        description=text["description"],
        dataset_codes=dataset_codes,
        policy=optional["policy"],
        footnote=optional["footnote"],
        lower_goalpost=lower,
        upper_goalpost=upper,
        score_function=optional["score_function"],
    )


def _parse_source(path: Path, record: dict, problems: _Problems) -> SourceMetadata | None:
    source = record.get("source")
    if not isinstance(source, dict):
        problems.add(path, f"field 'source' must be a mapping, got {source!r}")
        return None
    before = len(problems.items)
    _check_keys(source, SOURCE_KEYS, path, problems, context="source.")
    organization_code = _text(source, "organization_code", path, problems, required=True, context="source.")
    optional = {
        key: _text(source, key, path, problems, required=False, context="source.")
        for key in ("query_code", "organization_series_code", "organization_name", "base_url", "format", "note", "published_unit")
    }
    dimensions = _dimensions(source, path, problems)
    multiplier = _multiplier(source, path, problems)
    if len(problems.items) != before:
        return None
    return SourceMetadata(organization_code=organization_code, dimensions=dimensions, value_multiplier=multiplier, **optional)


def _dimensions(source: dict, path: Path, problems: _Problems) -> dict[str, str] | None:
    value = source.get("dimensions")
    if value is None:
        return None
    if not isinstance(value, dict) or not value or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in value.items()):
        problems.add(path, f"field 'source.dimensions' must be a non-empty mapping of strings to strings or null, got {value!r}")
        return None
    return dict(value)


def _multiplier(source: dict, path: Path, problems: _Problems) -> int | float | None:
    value = source.get("value_multiplier")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0 or value != value or value == float("inf"):
        problems.add(path, f"field 'source.value_multiplier' must be a positive finite number or null, got {value!r}")
        return None
    return value  # kept as written: an int factor multiplies exactly as the legacy cleaner's did


def parse_dataset(path: Path, record: dict, problems: _Problems) -> DatasetMetadata | UnresolvedDataset | None:
    status = record.get("status")
    if status not in STATUSES:
        problems.add(path, f"field 'status' must be one of {STATUSES}, got {status!r}")
        return None
    before = len(problems.items)
    if status == "unresolved":
        _check_keys(record, UNRESOLVED_KEYS, path, problems, context="(unresolved dataset) ")
        code = _text(record, "code", path, problems, required=True)
        note = _text(record, "note", path, problems, required=True)
        if len(problems.items) != before:
            return None
        return UnresolvedDataset(code=code, note=note)
    _check_keys(record, DATASET_KEYS, path, problems)
    code = _text(record, "code", path, problems, required=True)
    name = _text(record, "name", path, problems, required=True)
    dataset_type = _text(record, "dataset_type", path, problems, required=True)
    description = _text(record, "description", path, problems, required=False)
    unit = _text(record, "unit", path, problems, required=False)
    source = _parse_source(path, record, problems)
    if len(problems.items) != before:
        return None
    return DatasetMetadata(
        code=code, name=name, dataset_type=dataset_type, source=source, description=description, unit=unit
    )


# --------------------------------------------------------------------------- #
# Tree loading
# --------------------------------------------------------------------------- #


def _read_records(directory: Path, problems: _Problems) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = read_yaml(path)
        except yaml.YAMLError as exc:
            problems.add(path, f"invalid YAML: {exc}")
            continue
        if not isinstance(data, dict):
            problems.add(path, f"top level must be a mapping, got {type(data).__name__}")
            continue
        records.append((path, data))
    return records


def load_catalog_data(root: Path) -> CatalogData:
    """Read, validate, and cross-check every metadata file under ``root``."""
    root = Path(root)
    problems = _Problems(root)
    indicators_dir = root / "indicators"
    datasets_dir = root / "datasets"
    for directory in (indicators_dir, datasets_dir):
        if not directory.is_dir():
            problems.add(directory, "directory does not exist")
    problems.raise_if_any()

    indicators: dict[str, IndicatorMetadata] = {}
    indicator_paths: dict[str, Path] = {}
    # (path, code, dataset_codes) for every record, including ones that failed
    # field validation, so dangling references are reported in the same pass.
    reference_checks: list[tuple[Path, Any, tuple[str, ...]]] = []
    for path, record in _read_records(indicators_dir, problems):
        indicator = parse_indicator(path, record, problems)
        if indicator is None:
            reference_checks.append((path, record.get("code"), _well_formed_codes(record)))
            continue
        if indicator.code in indicators:
            problems.add(path, f"duplicate indicator code {indicator.code} (also defined in {problems.where(indicator_paths[indicator.code])})")
            continue
        indicators[indicator.code] = indicator
        indicator_paths[indicator.code] = path
        reference_checks.append((path, indicator.code, indicator.dataset_codes))

    datasets: dict[str, DatasetMetadata | UnresolvedDataset] = {}
    dataset_paths: dict[str, Path] = {}
    for path, record in _read_records(datasets_dir, problems):
        dataset = parse_dataset(path, record, problems)
        if dataset is None:
            continue
        if dataset.code in datasets:
            problems.add(path, f"duplicate dataset code {dataset.code} (also defined in {problems.where(dataset_paths[dataset.code])})")
            continue
        datasets[dataset.code] = dataset
        dataset_paths[dataset.code] = path

    if not indicators and not problems.items:
        problems.add(indicators_dir, "no indicator files found")

    for path, code, dataset_codes in reference_checks:
        for dataset_code in dataset_codes:
            if dataset_code not in datasets:
                problems.add(
                    path,
                    f"indicator {code} references unknown dataset {dataset_code} "
                    "(add a documented or an explicit unresolved dataset entry)",
                )

    problems.raise_if_any()
    return CatalogData(indicators=indicators, datasets=datasets)


def _well_formed_codes(record: dict) -> tuple[str, ...]:
    """Dataset codes from a record that failed validation, as far as they are usable."""
    value = record.get("dataset_codes")
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str) and v)
