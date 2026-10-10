"""The legacy metadata importer reproduces the checked-in canonical metadata.

``scripts/import_legacy_metadata.py`` reads the approved corrections from
``PROVENANCE.yaml`` (``edits`` and ``additions``) and holds no list of its
own, so a correction recorded there cannot be lost by regenerating.

Two layers:

* offline, always: every recorded correction is what the canonical file
  holds, and the importer carries no second list;
* against the legacy repository, when it is checked out next to this one at
  the pinned commit: a regeneration into a temporary directory is byte for
  byte the checked-in metadata. Skipped when the legacy repository is not
  available (set ``SSPI_LEGACY_REPO`` to point elsewhere).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parents[2]
DATA = REPO / "src" / "sspi" / "metadata" / "data"
IMPORTER = REPO / "scripts" / "import_legacy_metadata.py"
LEGACY = Path(os.environ.get("SSPI_LEGACY_REPO", REPO.parent / "sspi-data-webapp"))
PROVENANCE = yaml.safe_load((DATA / "PROVENANCE.yaml").read_text(encoding="utf-8"))


def canonical(file):
    return yaml.safe_load((DATA / file).read_text(encoding="utf-8"))


def field(record, dotted):
    for key in dotted.split("."):
        record = record[key]
    return record


@pytest.mark.parametrize("edit", PROVENANCE["edits"], ids=lambda e: f"{e['file']}:{e['field']}")
def test_every_recorded_edit_is_what_the_canonical_file_holds(edit):
    assert set(edit) == {"file", "field", "old", "new", "reason"} and edit["reason"]
    assert field(canonical(edit["file"]), edit["field"]) == edit["new"]


@pytest.mark.parametrize("addition", PROVENANCE["additions"], ids=lambda a: a["file"])
def test_every_recorded_addition_is_in_the_catalog_with_its_source_fields(addition):
    assert set(addition) == {"file", "source", "reason"} and addition["reason"]
    source = canonical(addition["file"])["source"]
    assert {key: source[key] for key in addition["source"]} == addition["source"]


def test_no_edit_is_recorded_twice():
    targets = [(e["file"], e["field"]) for e in PROVENANCE["edits"]]
    assert len(targets) == len(set(targets)) == 66
    assert len({e["file"] for e in PROVENANCE["edits"]}) == 40 and len(PROVENANCE["additions"]) == 1


def test_the_importer_holds_no_list_of_its_own():
    """PROVENANCE.yaml is the single record: none of its corrected values or reasons is repeated in the script."""
    script = IMPORTER.read_text(encoding="utf-8")
    assert "EDITS" not in script and "ADDITIONS" not in script
    for entry in PROVENANCE["edits"] + PROVENANCE["additions"]:
        assert entry["file"] not in script and entry["reason"] not in script


def legacy_checkout():
    """The legacy repository, if it is there, clean and at the commit the canonical metadata was imported from."""
    if not (LEGACY / ".git").exists():
        pytest.skip(f"legacy repository not found at {LEGACY}")
    head = subprocess.run(["git", "-C", str(LEGACY), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != PROVENANCE["source_commit"]:
        pytest.skip(f"legacy repository is at {head[:8]}, not the pinned {PROVENANCE['source_commit'][:8]}")
    if subprocess.run(["git", "-C", str(LEGACY), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip():
        pytest.skip("legacy repository has local changes")
    return LEGACY


def test_regenerating_reproduces_the_checked_in_metadata_byte_for_byte(tmp_path):
    legacy = legacy_checkout()
    before = {path.relative_to(DATA): path.read_bytes() for path in sorted(DATA.rglob("*.yaml"))}
    subprocess.run([sys.executable, str(IMPORTER), "--old-repo", str(legacy), "--output-dir", str(tmp_path)], capture_output=True, text=True, check=True)
    regenerated = {path.relative_to(tmp_path): path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()}
    assert sorted(regenerated) == sorted(before) and len(before) == 57 + 90 + 2
    assert [str(name) for name in before if regenerated[name] != before[name]] == []
    assert {path.relative_to(DATA): path.read_bytes() for path in sorted(DATA.rglob("*.yaml"))} == before  # the canonical directory was not written to
