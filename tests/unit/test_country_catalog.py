"""CountryCatalog behaviour on the bundled canonical country groups.

The bundled file is a verbatim copy of the legacy ``local/country-groups.json``:
group order, member order and memberships are those of the source. Tests
here pin that fidelity and the catalog API; ``test_golden_countries.py``
compares against the legacy builders' output.
"""

import dataclasses

import pytest

import sspi.metadata.loader as loader
from sspi.errors import UnknownCodeError
from sspi.metadata import Country, CountryCatalog, CountryGroup

LEGACY_GROUP_ORDER = ("SSPI49", "SSPIExtended", "SSPI67", "G20", "OECD", "BRICS", "EU28", "NonSSPI")


@pytest.fixture(scope="module")
def catalog():
    return CountryCatalog.load()


# --- groups ----------------------------------------------------------------


def test_groups_come_back_in_legacy_source_order(catalog):
    assert tuple(g.code for g in catalog.groups()) == LEGACY_GROUP_ORDER


def test_sspi67_is_the_legacy_list_verbatim(catalog):
    group = catalog.group("SSPI67")
    assert isinstance(group, CountryGroup)
    assert group.code == "SSPI67"
    assert len(group.members) == 66  # the legacy "67" has 66 members; not corrected
    assert group.members[:8] == ("ARG", "AUS", "AUT", "BEL", "BRA", "CAN", "CHL", "CHN")
    assert group.members[-1] == "VNM"
    assert group.members != tuple(sorted(group.members))  # source order kept, not sorted


def test_sspi67_is_sspi49_followed_by_sspi_extended(catalog):
    assert catalog.group("SSPI67").members == catalog.group("SSPI49").members + catalog.group("SSPIExtended").members


def test_group_sizes(catalog):
    assert {g.code: len(g.members) for g in catalog.groups()} == {
        "SSPI49": 49,
        "SSPIExtended": 17,
        "SSPI67": 66,
        "G20": 19,
        "OECD": 36,
        "BRICS": 5,
        "EU28": 28,
        "NonSSPI": 179,
    }


def test_members_are_immutable_tuples(catalog):
    members = catalog.group("BRICS").members
    assert isinstance(members, tuple)
    assert members == ("BRA", "RUS", "IND", "CHN", "ZAF")
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog.group("BRICS").code = "X"


def test_unknown_group_raises_unknown_code_error(catalog):
    with pytest.raises(UnknownCodeError, match="SSPI68"):
        catalog.group("SSPI68")
    assert issubclass(UnknownCodeError, KeyError)


def test_group_lookup_is_exact_case(catalog):
    # Legacy matched group names case-insensitively via regex; every call site used exact case.
    with pytest.raises(UnknownCodeError):
        catalog.group("sspi67")


# --- countries ---------------------------------------------------------------


def test_country_identity_is_iso3_with_pycountry_name(catalog):
    austria = catalog.country("AUT")
    assert isinstance(austria, Country)
    assert austria.code == "AUT"
    assert austria.name == "Austria"
    assert austria.groups == ("SSPI49", "SSPI67", "OECD", "EU28")  # legacy group order, not sorted
    assert catalog.country("MYS").name == "Malaysia"
    assert catalog.country("MYS").groups == ("SSPIExtended", "SSPI67")


def test_country_has_only_the_legacy_fields(catalog):
    # No landlocked flag, no region, no population: nothing the legacy source did not hold.
    assert [f.name for f in dataclasses.fields(Country)] == ["code", "name", "groups"]
    assert [f.name for f in dataclasses.fields(CountryGroup)] == ["code", "members"]


def test_country_universe_is_the_union_of_group_members(catalog):
    codes = [c.code for c in catalog.countries()]
    assert codes == sorted(codes)
    assert len(codes) == 249
    assert set(codes) == {m for g in catalog.groups() for m in g.members}


def test_groups_for_matches_country_groups(catalog):
    assert catalog.groups_for("MYS") == ("SSPIExtended", "SSPI67")
    assert catalog.groups_for("ABW") == ("NonSSPI",)
    assert catalog.groups_for("AUT") == catalog.country("AUT").groups


def test_unknown_country_raises_unknown_code_error(catalog):
    with pytest.raises(UnknownCodeError, match="XKX"):
        catalog.country("XKX")
    with pytest.raises(UnknownCodeError, match="XKX"):
        catalog.groups_for("XKX")


# --- legacy facts preserved, not corrected -------------------------------------------


def test_non_sspi_is_not_the_complement_of_sspi67(catalog):
    # Legacy inconsistency kept as-is: four EU28 members are in neither SSPI67 nor NonSSPI.
    sspi67, non_sspi = set(catalog.group("SSPI67").members), set(catalog.group("NonSSPI").members)
    assert not (sspi67 & non_sspi)
    assert {c.code for c in catalog.countries()} - sspi67 - non_sspi == {"BGR", "CYP", "HRV", "MLT"}
    assert catalog.groups_for("MLT") == ("EU28",)


def test_landlocked_sspi67_members_are_plain_members(catalog):
    # These are the SSPI67 countries with no marine series at the UN source. The catalog
    # records nothing about that: the BIODIV treatment is an open methodology decision.
    members = set(catalog.group("SSPI67").members)
    assert {"AUT", "CHE", "CZE", "ETH", "HUN", "LUX", "SVK"} <= members


# --- loading ----------------------------------------------------------------------


def test_queries_do_not_reread_files(catalog, monkeypatch):
    def boom(path):
        raise AssertionError(f"re-read {path}")

    monkeypatch.setattr(loader, "read_yaml", boom)
    assert catalog.group("SSPI67").members[0] == "ARG"
    assert catalog.country("AUT").name == "Austria"
    assert len(catalog.countries()) == 249


def test_loading_twice_gives_equal_catalogs():
    a, b = CountryCatalog.load(), CountryCatalog.load()
    assert [g for g in a.groups()] == [g for g in b.groups()]
    assert [c for c in a.countries()] == [c for c in b.countries()]
