"""normalize_unsdg_dataset: pure conversion of UN SDG pivot rows into Observations.

Uses the committed fixture (verbatim live rows for 14.5.1) plus small
synthetic rows for cases the real data does not exhibit.
"""

import copy
import json
from pathlib import Path

import pytest

from sspi.errors import DuplicateObservationError, NormalizationError
from sspi.ingestion.unsdg import NormalizationResult, normalize_unsdg_dataset
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata, UnresolvedDataset
from sspi.scoring import Observation

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "unsdg" / "14_5_1_sample.json").read_text())


@pytest.fixture(scope="module")
def marine() -> DatasetMetadata:
    return MetadataCatalog.load().dataset("UNSDG_MARINE")


@pytest.fixture
def rows():
    return copy.deepcopy(FIXTURE["data"])


def entry(year, value, **attrs):
    base = {"year": f"[{year}]", "value": value, "valueType": "Float", "footnotes": "", "Nature": "C", "Source Type": "",
            "UnitMultiplier": "", "Units": "PERCENT", "Management Level": "", "Observation Status": "A", "Geo Info Type": ""}
    base.update(attrs)
    return base


def row(series="ER_MRN_MPA", geo="458", name="Malaysia", entries=(), units="PERCENT", **dims):
    r = {"goal": "14", "target": "14.5", "indicator": "14.5.1", "series": series, "seriesDescription": "desc", "seriesCount": "1",
         "geoAreaCode": geo, "geoAreaName": name, "units": units, "sex": None, "age": None, "location": None, "reporting_type": None,
         "years": json.dumps(list(entries))}
    r.update(dims)
    return r


def by_key(result):
    return {(o.country_code, o.year): o for o in result.observations}


# --- fixture-driven behaviour ------------------------------------------------


def test_fixture_normalizes_to_expected_shape(marine, rows):
    result = normalize_unsdg_dataset(marine, rows)
    assert isinstance(result, NormalizationResult)
    assert all(isinstance(o, Observation) for o in result.observations)
    assert {o.country_code for o in result.observations} == {"MYS", "USA", "KEN", "ALB"}
    assert len(result.observations) == 4 * 26
    assert result.skipped_areas == (("1", "World"), ("150", "Europe"))
    assert result.missing_values == 4 * 38  # mapped areas only: 64 year entries each, 26 filled


def test_output_is_sorted_by_country_then_year(marine, rows):
    observations = normalize_unsdg_dataset(marine, rows).observations
    assert [(o.country_code, o.year) for o in observations] == sorted((o.country_code, o.year) for o in observations)


def test_year_and_value_extraction_for_malaysia(marine, rows):
    mys = by_key(normalize_unsdg_dataset(marine, rows))
    assert mys[("MYS", 2004)].value == 10.52543
    assert mys[("MYS", 2016)].value == 19.70109
    assert mys[("MYS", 2000)].value == 10.49717
    assert min(y for c, y in mys if c == "MYS") == 2000
    assert max(y for c, y in mys if c == "MYS") == 2025  # source carries future years; kept, not constrained


def test_canonical_unit_and_dataset_code(marine, rows):
    for o in normalize_unsdg_dataset(marine, rows).observations:
        assert o.dataset_code == "UNSDG_MARINE"
        assert o.unit == "PERCENT"


def test_provenance_contents(marine, rows):
    obs = by_key(normalize_unsdg_dataset(marine, rows))[("MYS", 2004)]
    assert obs.provenance == {
        "source_organization": "UNSDG",
        "source_indicator": "14.5.1",
        "source_series": "ER_MRN_MPA",
        "source_geo_area_code": "458",
        "source_geo_area_name": "Malaysia",
        "nature": "C",
        "observation_status": "A",
    }


def test_provenance_carries_no_volatile_values(marine, rows):
    a = normalize_unsdg_dataset(marine, rows).observations
    b = normalize_unsdg_dataset(marine, copy.deepcopy(FIXTURE["data"])).observations
    assert a == b


def test_input_rows_are_not_mutated(marine, rows):
    before = copy.deepcopy(rows)
    normalize_unsdg_dataset(marine, rows)
    assert rows == before


# --- series selection and dimensions ------------------------------------------


def test_only_the_canonical_series_is_kept(marine):
    rows = [row(series="ER_MRN_MPA", entries=[entry(2020, "60")]), row(series="ER_MRN_MPAKMSQ", units="KMSQ", entries=[entry(2020, "12", Units="KMSQ")])]
    result = normalize_unsdg_dataset(marine, rows)
    assert [(o.country_code, o.year, o.value) for o in result.observations] == [("MYS", 2020, 60.0)]


def test_no_rows_for_series_fails(marine):
    with pytest.raises(NormalizationError, match="ER_MRN_MPA"):
        normalize_unsdg_dataset(marine, [row(series="ER_PTD_TERR", entries=[entry(2020, "1")])])


def test_duplicate_identity_from_an_unpinned_dimension_fails_clearly(marine):
    rows = [
        row(entries=[entry(2020, "60")], reporting_type="N"),
        row(entries=[entry(2020, "61")], reporting_type="G"),
    ]
    with pytest.raises(DuplicateObservationError) as info:
        normalize_unsdg_dataset(marine, rows)
    message = str(info.value)
    assert "('MYS', 2020)" in message and "reporting_type" in message


def test_dimension_filter_selects_exactly_one_slice(marine):
    rows = [
        row(entries=[entry(2020, "60")], reporting_type="N"),
        row(entries=[entry(2020, "61")], reporting_type="G"),
    ]
    result = normalize_unsdg_dataset(marine, rows, dimension_filters={"reporting_type": "G"})
    assert [(o.year, o.value) for o in result.observations] == [(2020, 61.0)]


def test_dimension_filter_that_matches_nothing_fails(marine):
    with pytest.raises(NormalizationError, match="reporting_type"):
        normalize_unsdg_dataset(marine, [row(entries=[entry(2020, "60")], reporting_type="N")], dimension_filters={"reporting_type": "G"})


def test_duplicate_year_within_one_area_row_fails(marine):
    with pytest.raises(DuplicateObservationError):
        normalize_unsdg_dataset(marine, [row(entries=[entry(2020, "60"), entry(2020, "61")])])


# --- countries -------------------------------------------------------------------


def test_aggregates_and_unmapped_areas_are_skipped_and_reported(marine):
    rows = [row(geo="1", name="World", entries=[entry(2020, "1")]), row(geo="999", name="Nowhere", entries=[entry(2020, "1")]), row(geo="840", name="United States of America", entries=[entry(2020, "2")])]
    result = normalize_unsdg_dataset(marine, rows)
    assert [o.country_code for o in result.observations] == ["USA"]
    assert result.skipped_areas == (("1", "World"), ("999", "Nowhere"))


def test_territories_with_iso_numeric_codes_are_kept_as_legacy_did(marine):
    result = normalize_unsdg_dataset(marine, [row(geo="630", name="Puerto Rico", entries=[entry(2020, "5")])])
    assert [o.country_code for o in result.observations] == ["PRI"]


def test_m49_codes_are_zero_padded_before_lookup(marine):
    result = normalize_unsdg_dataset(marine, [row(geo="8", name="Albania", entries=[entry(2020, "5")])])
    assert [o.country_code for o in result.observations] == ["ALB"]


# --- years ------------------------------------------------------------------


@pytest.mark.parametrize("bad_year", ["[2019-2020]", "2020", "[20200]", "", None])
def test_non_single_year_strings_fail(marine, bad_year):
    bad = entry(2020, "60")
    bad["year"] = bad_year
    with pytest.raises(NormalizationError, match="year"):
        normalize_unsdg_dataset(marine, [row(entries=[bad])])


# --- values --------------------------------------------------------------------


def test_empty_null_and_nan_values_are_missing_not_errors(marine):
    """The legacy extractor dropped empty and NaN values alike; 6.4.1 really does publish the string "NaN"."""
    result = normalize_unsdg_dataset(marine, [row(entries=[{"year": "[2019]", "value": ""}, {"year": "[2020]", "value": None}, entry(2021, "3"), entry(2022, "NaN")])])
    assert [(o.year, o.value) for o in result.observations] == [(2021, 3.0)]
    assert result.missing_values == 3


@pytest.mark.parametrize("bad_value", ["NA", "n/a", "1,5", "12 %", "abc", "inf", "-Infinity"])
def test_non_empty_malformed_values_fail(marine, bad_value):
    with pytest.raises(NormalizationError, match="value"):
        normalize_unsdg_dataset(marine, [row(entries=[entry(2020, bad_value)])])


def test_numeric_strings_and_numbers_are_accepted(marine):
    result = normalize_unsdg_dataset(marine, [row(entries=[entry(2019, "25.49229"), entry(2020, 7), entry(2021, "1e1"), entry(2022, "0")])])
    assert [o.value for o in result.observations] == [25.49229, 7.0, 10.0, 0.0]


# --- units ------------------------------------------------------------------


def test_row_unit_disagreeing_with_canonical_unit_fails(marine):
    with pytest.raises(NormalizationError, match="PERCENT"):
        normalize_unsdg_dataset(marine, [row(units="KMSQ", entries=[entry(2020, "60")])])


def test_entry_unit_disagreeing_with_canonical_unit_fails(marine):
    with pytest.raises(NormalizationError, match="KMSQ"):
        normalize_unsdg_dataset(marine, [row(entries=[entry(2020, "60", Units="KMSQ")])])


def test_unit_multiplier_is_never_applied(marine):
    with pytest.raises(NormalizationError, match="multiplier"):
        normalize_unsdg_dataset(marine, [row(entries=[entry(2020, "60", UnitMultiplier="3")])])


# --- flags: preserved, never filtered (legacy-compatible) -----------------------


def test_nature_n_survives_into_provenance_as_legacy_compatible_behavior(marine):
    # Legacy ingested Nature=N ("non-relevant") values as ordinary data. Preserved here so the
    # question can be revisited; this is NOT a decision that such values suit BIODIV.
    result = normalize_unsdg_dataset(marine, [row(entries=[entry(2020, "0", Nature="N", **{"Observation Status": "E"})])])
    (obs,) = result.observations
    assert obs.value == 0.0
    assert obs.provenance["nature"] == "N"
    assert obs.provenance["observation_status"] == "E"


def test_footnotes_kept_only_when_present(marine):
    result = normalize_unsdg_dataset(marine, [row(entries=[entry(2019, "1", footnotes="Break in series"), entry(2020, "2")])])
    a, b = result.observations
    assert a.provenance["footnotes"] == "Break in series"
    assert "footnotes" not in b.provenance


# --- inputs and metadata --------------------------------------------------------


def test_unresolved_dataset_is_rejected():
    with pytest.raises(NormalizationError, match="IMF_FSTABL"):
        normalize_unsdg_dataset(UnresolvedDataset("IMF_FSTABL", "no definition"), [row()])


def test_non_unsdg_dataset_is_rejected():
    wb = DatasetMetadata("WB_POPULN", "Population", "Indicator", SourceMetadata("WB", "SP.POP.TOTL"), unit="People")
    with pytest.raises(NormalizationError, match="UNSDG"):
        normalize_unsdg_dataset(wb, [row()])


def test_dataset_without_series_code_is_rejected():
    ds = DatasetMetadata("UNSDG_X", "X", "Intermediate", SourceMetadata("UNSDG", "14.5.1", None), unit="PERCENT")
    with pytest.raises(NormalizationError, match="series"):
        normalize_unsdg_dataset(ds, [row()])


@pytest.mark.parametrize("bad_years", ["not json", '{"a": 1}', 12])
def test_malformed_years_field_fails(marine, bad_years):
    bad = row(entries=[])
    bad["years"] = bad_years
    with pytest.raises(NormalizationError, match="years"):
        normalize_unsdg_dataset(marine, [bad])


def test_years_may_already_be_a_list(marine):
    r = row(entries=[])
    r["years"] = [entry(2020, "4")]
    assert [o.value for o in normalize_unsdg_dataset(marine, [r]).observations] == [4.0]
