"""UNSDG_TERRST and UNSDG_FRSHWT through the unchanged UNSDG pipeline, plus the
three BIODIV datasets side by side.

Both datasets come from one 15.1.2 payload and differ only by series. The
committed fixture holds both series for the same areas, including Austria, a
landlocked country that the marine source (14.5.1) does not report at all.
"""

import copy
import json
from pathlib import Path

import pytest

from sspi.errors import DuplicateObservationError, NormalizationError
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
F15 = json.loads((FIXTURES / "15_1_2_sample.json").read_text())
F14 = json.loads((FIXTURES / "14_5_1_sample.json").read_text())

SERIES = {"UNSDG_MARINE": "ER_MRN_MPA", "UNSDG_TERRST": "ER_PTD_TERR", "UNSDG_FRSHWT": "ER_PTD_FRHWTR"}
FIXTURE_FOR = {"UNSDG_MARINE": F14, "UNSDG_TERRST": F15, "UNSDG_FRSHWT": F15}
LANDLOCKED_CODE, LANDLOCKED_ISO = "40", "AUT"  # Austria


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


@pytest.fixture
def rows15():
    return copy.deepcopy(F15["data"])


def by_key(result):
    return {(o.country_code, o.year): o for o in result.observations}


# --- metadata --------------------------------------------------------------


def test_biodiv_dependencies_are_three_distinct_unsdg_series(catalog):
    deps = catalog.dataset_dependencies("BIODIV")
    assert [d.code for d in deps] == ["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"]
    assert {d.source.organization_code for d in deps} == {"UNSDG"}
    assert {d.code: d.source.organization_series_code for d in deps} == SERIES
    assert {d.code: d.source.query_code for d in deps} == {"UNSDG_MARINE": "14.5.1", "UNSDG_TERRST": "15.1.2", "UNSDG_FRSHWT": "15.1.2"}
    assert {d.unit for d in deps} == {"PERCENT"}


# --- series selection from the shared payload ------------------------------------


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
def test_series_selection_and_shape(catalog, rows15, code):
    result = normalize_unsdg_dataset(catalog.dataset(code), rows15)
    assert {o.dataset_code for o in result.observations} == {code}
    assert {o.unit for o in result.observations} == {"PERCENT"}
    assert {o.country_code for o in result.observations} == {"MYS", "USA", "KEN", "AUT"}
    assert len(result.observations) == 4 * 26
    assert result.skipped_areas == (("1", "World"), ("150", "Europe"))
    assert result.missing_values == 4 * 38
    assert {o.provenance["source_series"] for o in result.observations} == {SERIES[code]}
    assert {o.provenance["source_indicator"] for o in result.observations} == {"15.1.2"}


def test_one_payload_yields_two_distinct_canonical_datasets(catalog, rows15):
    terrst = normalize_unsdg_dataset(catalog.dataset("UNSDG_TERRST"), rows15)
    frshwt = normalize_unsdg_dataset(catalog.dataset("UNSDG_FRSHWT"), rows15)
    t, f = by_key(terrst), by_key(frshwt)
    assert set(t) == set(f)  # same countries and years in this fixture
    assert all(t[k].dataset_code == "UNSDG_TERRST" and f[k].dataset_code == "UNSDG_FRSHWT" for k in t)
    assert t[("MYS", 2020)].value != f[("MYS", 2020)].value
    assert not (set(terrst.observations) & set(frshwt.observations))


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
def test_no_identity_collisions(catalog, rows15, code):
    identities = [(o.country_code, o.year) for o in normalize_unsdg_dataset(catalog.dataset(code), rows15).observations]
    assert len(identities) == len(set(identities))


def test_malaysia_values_from_source(catalog, rows15):
    t = by_key(normalize_unsdg_dataset(catalog.dataset("UNSDG_TERRST"), rows15))
    f = by_key(normalize_unsdg_dataset(catalog.dataset("UNSDG_FRSHWT"), rows15))
    assert t[("MYS", 2020)].value == 37.03085
    assert f[("MYS", 2020)].value == 32.45402
    assert min(y for c, y in t if c == "MYS") == 2000 and max(y for c, y in t if c == "MYS") == 2025


def test_provenance_contents(catalog, rows15):
    obs = by_key(normalize_unsdg_dataset(catalog.dataset("UNSDG_FRSHWT"), rows15))[("KEN", 2015)]
    assert obs.provenance == {
        "source_organization": "UNSDG",
        "source_indicator": "15.1.2",
        "source_series": "ER_PTD_FRHWTR",
        "source_geo_area_code": "404",
        "source_geo_area_name": "Kenya",
        "nature": "C",
        "observation_status": "A",
    }


# --- landlocked-country regression: source-level reality, no filling ---------------


def test_landlocked_country_present_in_terrestrial_and_freshwater_but_absent_from_marine(catalog, rows15):
    terrst = normalize_unsdg_dataset(catalog.dataset("UNSDG_TERRST"), rows15)
    frshwt = normalize_unsdg_dataset(catalog.dataset("UNSDG_FRSHWT"), rows15)
    marine = normalize_unsdg_dataset(catalog.dataset("UNSDG_MARINE"), copy.deepcopy(F14["data"]))

    assert sum(o.country_code == LANDLOCKED_ISO for o in terrst.observations) == 26
    assert sum(o.country_code == LANDLOCKED_ISO for o in frshwt.observations) == 26
    assert not any(o.country_code == LANDLOCKED_ISO for o in marine.observations)

    # The absence is a property of the source, not of the fixture subset: the full 14.5.1
    # response contains no row for this area, while both 15.1.2 series do.
    assert LANDLOCKED_CODE not in F14["_full_response_geo_area_codes"]["ER_MRN_MPA"]
    assert LANDLOCKED_CODE in F15["_full_response_geo_area_codes"]["ER_PTD_TERR"]
    assert LANDLOCKED_CODE in F15["_full_response_geo_area_codes"]["ER_PTD_FRHWTR"]
    # Nothing is filled, synthesized, or imputed here. The BIODIV treatment of countries
    # without a marine series is a methodology decision for the imputation/scoring stage.
    assert (LANDLOCKED_ISO, 2020) not in by_key(marine)


# --- established rules apply unchanged to the new datasets --------------------------


def series_row(code, geo="458", name="Malaysia", value="50", units="PERCENT", **entry_overrides):
    entry = {"year": "[2020]", "value": value, "Nature": "C", "Observation Status": "A", "Units": "PERCENT", "UnitMultiplier": ""}
    entry.update(entry_overrides)
    return {"series": SERIES[code], "geoAreaCode": geo, "geoAreaName": name, "units": units, "reporting_type": None, "years": json.dumps([entry])}


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
def test_unit_disagreement_fails(catalog, code):
    with pytest.raises(NormalizationError, match="PERCENT"):
        normalize_unsdg_dataset(catalog.dataset(code), [series_row(code, units="KMSQ")])


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
@pytest.mark.parametrize("bad", ["NA", "12 %", "inf"])
def test_malformed_values_fail(catalog, code, bad):
    with pytest.raises(NormalizationError, match="value"):
        normalize_unsdg_dataset(catalog.dataset(code), [series_row(code, value=bad)])


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
def test_empty_values_are_missing_and_aggregates_skipped(catalog, code):
    result = normalize_unsdg_dataset(catalog.dataset(code), [series_row(code, value=""), series_row(code, geo="1", name="World")])
    assert result.observations == []
    assert result.missing_values == 1
    assert result.skipped_areas == (("1", "World"),)


@pytest.mark.parametrize("code", ["UNSDG_TERRST", "UNSDG_FRSHWT"])
def test_unpinned_dimension_collision_fails(catalog, code):
    rows = [series_row(code), {**series_row(code, value="51"), "reporting_type": "G"}]
    with pytest.raises(DuplicateObservationError, match="reporting_type"):
        normalize_unsdg_dataset(catalog.dataset(code), rows)


def test_wrong_series_in_payload_fails_clearly(catalog):
    with pytest.raises(NormalizationError, match="ER_PTD_TERR"):
        normalize_unsdg_dataset(catalog.dataset("UNSDG_TERRST"), [series_row("UNSDG_MARINE")])
