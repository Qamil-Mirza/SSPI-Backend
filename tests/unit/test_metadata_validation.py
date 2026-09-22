"""Loader validation on small synthetic metadata trees.

Every problem must be reported, never silently ignored, and all problems in a
tree are reported together in one MetadataError.
"""

from pathlib import Path

import pytest
import yaml

from sspi.errors import MetadataError
from sspi.metadata import MetadataCatalog, UnresolvedDataset


def write(root: Path, rel: str, data) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False)
    path.write_text(text)
    return path


def indicator(code="IND001", **overrides) -> dict:
    record = {
        "code": code,
        "name": f"Indicator {code}",
        "pillar_code": "SUS",
        "category_code": "ECO",
        "policy": "Some policy",
        "description": "Some description",
        "footnote": None,
        "dataset_codes": ["DS_A"],
        "lower_goalpost": 0,
        "upper_goalpost": 100,
        "score_function": "Score = goalpost(DS_A, 0, 100)",
    }
    record.update(overrides)
    return record


def dataset(code="DS_A", **overrides) -> dict:
    record = {
        "code": code,
        "status": "documented",
        "name": f"Dataset {code}",
        "dataset_type": "Intermediate",
        "description": "Some description",
        "unit": "Percent",
        "source": {"organization_code": "ORG", "organization_series_code": None, "query_code": "Q1"},
    }
    record.update(overrides)
    return record


def unresolved(code="DS_U", **overrides) -> dict:
    record = {"code": code, "status": "unresolved", "note": "No legacy definition."}
    record.update(overrides)
    return record


@pytest.fixture
def tree(tmp_path):
    write(tmp_path, "indicators/IND001.yaml", indicator())
    write(tmp_path, "datasets/DS_A.yaml", dataset())
    return tmp_path


def load_error(root) -> str:
    with pytest.raises(MetadataError) as info:
        MetadataCatalog.load(root)
    return str(info.value)


def test_minimal_tree_loads(tree):
    catalog = MetadataCatalog.load(tree)
    assert catalog.indicator("IND001").dataset_codes == ("DS_A",)
    assert catalog.dataset("DS_A").source.query_code == "Q1"
    assert catalog.indicator("IND001").lower_goalpost == 0.0


def test_unresolved_entry_is_accepted_and_typed(tree):
    write(tree, "indicators/IND002.yaml", indicator("IND002", dataset_codes=["DS_U"]))
    write(tree, "datasets/DS_U.yaml", unresolved())
    catalog = MetadataCatalog.load(tree)
    (dep,) = catalog.dataset_dependencies("IND002")
    assert isinstance(dep, UnresolvedDataset)
    assert dep.note == "No legacy definition."


def test_duplicate_indicator_code_fails(tree):
    write(tree, "indicators/other.yaml", indicator("IND001"))
    message = load_error(tree)
    assert "duplicate indicator code IND001" in message
    assert "other.yaml" in message and "IND001.yaml" in message


def test_duplicate_dataset_code_fails_including_documented_versus_unresolved(tree):
    write(tree, "datasets/DS_A_again.yaml", unresolved("DS_A"))
    message = load_error(tree)
    assert "duplicate dataset code DS_A" in message


def test_dangling_dataset_reference_fails(tree):
    write(tree, "indicators/IND001.yaml", indicator(dataset_codes=["DS_A", "DS_MISSING"]))
    message = load_error(tree)
    assert "IND001" in message and "DS_MISSING" in message
    assert "unknown dataset" in message


def test_unknown_key_fails(tree):
    write(tree, "indicators/IND001.yaml", indicator(extra_key=1))
    assert "unknown key" in load_error(tree) and "extra_key" in load_error(tree)


def test_unknown_source_key_fails(tree):
    write(tree, "datasets/DS_A.yaml", dataset(source={"organization_code": "ORG", "query_code": "Q", "Filename": "x"}))
    assert "Filename" in load_error(tree)


def test_invalid_yaml_fails(tree):
    write(tree, "datasets/DS_A.yaml", "code: [unclosed\n")
    message = load_error(tree)
    assert "DS_A.yaml" in message and "YAML" in message


def test_non_mapping_file_fails(tree):
    write(tree, "datasets/DS_A.yaml", "- just\n- a list\n")
    assert "mapping" in load_error(tree)


def test_bad_status_fails(tree):
    write(tree, "datasets/DS_A.yaml", dataset(status="maybe"))
    assert "status" in load_error(tree)


@pytest.mark.parametrize("bad", ["0", True, [0]])
def test_non_numeric_goalpost_fails(tree, bad):
    write(tree, "indicators/IND001.yaml", indicator(lower_goalpost=bad))
    assert "lower_goalpost" in load_error(tree)


@pytest.mark.parametrize("field", ["code", "name", "pillar_code", "category_code", "description"])
def test_missing_or_empty_required_indicator_field_fails(tree, field):
    write(tree, "indicators/IND001.yaml", indicator(**{field: ""}))
    assert field in load_error(tree)
    record = indicator()
    del record[field]
    write(tree, "indicators/IND001.yaml", record)
    assert field in load_error(tree)


@pytest.mark.parametrize("bad", [[], ["DS_A", "DS_A"], "DS_A", [""], [1]])
def test_bad_dataset_codes_fail(tree, bad):
    write(tree, "indicators/IND001.yaml", indicator(dataset_codes=bad))
    assert "dataset_codes" in load_error(tree)


def test_missing_source_organization_code_fails(tree):
    write(tree, "datasets/DS_A.yaml", dataset(source={"query_code": "Q1"}))
    assert "organization_code" in load_error(tree)


def test_unresolved_entry_with_extra_fields_fails(tree):
    write(tree, "indicators/IND001.yaml", indicator(dataset_codes=["DS_U"]))
    write(tree, "datasets/DS_U.yaml", unresolved(name="Known after all"))
    message = load_error(tree)
    assert "unresolved" in message and "name" in message


def test_unresolved_entry_requires_note(tree):
    write(tree, "indicators/IND001.yaml", indicator(dataset_codes=["DS_U"]))
    write(tree, "datasets/DS_U.yaml", {"code": "DS_U", "status": "unresolved"})
    assert "note" in load_error(tree)


def test_independent_problems_are_reported_together(tree):
    write(tree, "indicators/IND001.yaml", indicator(dataset_codes=["DS_MISSING"], upper_goalpost="high"))
    message = load_error(tree)
    assert "DS_MISSING" in message
    assert "upper_goalpost" in message


def test_missing_directories_fail(tmp_path):
    assert "indicators" in load_error(tmp_path)
    (tmp_path / "indicators").mkdir()
    assert "datasets" in load_error(tmp_path)


def test_empty_tree_fails(tmp_path):
    (tmp_path / "indicators").mkdir()
    (tmp_path / "datasets").mkdir()
    assert "no indicator" in load_error(tmp_path)


def test_non_yaml_files_are_ignored(tree):
    write(tree, "indicators/README.md", "not metadata")
    write(tree, "datasets/notes.txt", "not metadata")
    assert len(MetadataCatalog.load(tree).indicators()) == 1
