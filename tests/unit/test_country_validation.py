"""CountryCatalog loading on small synthetic files.

Every problem is reported, all problems in a file are reported together in one
MetadataError, and a member code pycountry does not know fails loudly instead
of being silently dropped as the legacy loader did.
"""

from pathlib import Path

import pytest
import yaml

from sspi.errors import MetadataError
from sspi.metadata import CountryCatalog


def write(tmp_path: Path, data, name="country_groups.yaml") -> Path:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False))
    return path


def groups(*entries) -> dict:
    return {"groups": [{"code": code, "members": list(members)} for code, members in entries]}


def test_minimal_valid_file_loads(tmp_path):
    catalog = CountryCatalog.load(write(tmp_path, groups(("G1", ["MYS", "AUT"]), ("G2", ["AUT"]))))
    assert [g.code for g in catalog.groups()] == ["G1", "G2"]
    assert catalog.group("G1").members == ("MYS", "AUT")
    assert catalog.country("AUT").groups == ("G1", "G2")
    assert [c.code for c in catalog.countries()] == ["AUT", "MYS"]


def test_missing_file(tmp_path):
    with pytest.raises(MetadataError, match="does not exist"):
        CountryCatalog.load(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "content, message",
    [
        ("- just\n- a list\n", "must be a mapping"),
        ("groups: []\n", "non-empty list"),
        ("groups: {}\n", "non-empty list"),
        ("{}\n", "missing required field 'groups'"),
    ],
)
def test_top_level_shape(tmp_path, content, message):
    with pytest.raises(MetadataError, match=message):
        CountryCatalog.load(write(tmp_path, content))


def test_unknown_keys_rejected(tmp_path):
    data = groups(("G1", ["MYS"]))
    data["extra"] = 1
    data["groups"][0]["name"] = "Group One"
    with pytest.raises(MetadataError) as excinfo:
        CountryCatalog.load(write(tmp_path, data))
    assert "unknown key 'extra'" in str(excinfo.value)
    assert "unknown key groups[0].'name'" in str(excinfo.value)


def test_duplicate_group_code(tmp_path):
    with pytest.raises(MetadataError, match="duplicate group code G1"):
        CountryCatalog.load(write(tmp_path, groups(("G1", ["MYS"]), ("G1", ["AUT"]))))


def test_duplicate_member_within_group(tmp_path):
    # The legacy file once listed COL twice in SSPI67; the new loader refuses that.
    with pytest.raises(MetadataError, match="duplicate member 'COL' in group G1"):
        CountryCatalog.load(write(tmp_path, groups(("G1", ["COL", "MYS", "COL"]))))


@pytest.mark.parametrize("bad", ["XKX", "aut", "AU", "USA1", "", 840])
def test_member_must_be_current_iso3_alpha3(tmp_path, bad):
    with pytest.raises(MetadataError, match="ISO 3166-1 alpha-3"):
        CountryCatalog.load(write(tmp_path, groups(("G1", ["MYS", bad]))))


def test_group_needs_code_and_members(tmp_path):
    with pytest.raises(MetadataError) as excinfo:
        CountryCatalog.load(write(tmp_path, {"groups": [{"members": ["MYS"]}, {"code": "G2"}, {"code": "G3", "members": []}]}))
    text = str(excinfo.value)
    assert "groups[0].'code'" in text
    assert "groups[1].'members'" in text
    assert "groups[2].'members' must be a non-empty list" in text


def test_all_problems_reported_together(tmp_path):
    data = groups(("G1", ["MYS", "MYS", "XKX"]), ("G1", ["AUT"]))
    data["extra"] = True
    with pytest.raises(MetadataError) as excinfo:
        CountryCatalog.load(write(tmp_path, data))
    text = str(excinfo.value)
    assert "4 problem(s)" in text
    for expected in ("unknown key 'extra'", "duplicate member 'MYS'", "'XKX'", "duplicate group code G1"):
        assert expected in text
