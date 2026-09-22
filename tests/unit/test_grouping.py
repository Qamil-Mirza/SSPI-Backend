"""Translated from the old tests/unit/utilities/test_group_by_indicator.py.

Old `group_by_indicator` built one dict per (CountryCode, Year) with a nested
`Datasets` list. The new `group_observations` builds one `ObservationGroup`
per (country_code, year) with an `inputs` tuple. Assertions on positional
`Datasets[i]["DatasetCode"]` become assertions on `inputs[i].dataset_code`.

Dropped (representation-only):
- test_group_by_indicator_missing_required_fields: pinned `KeyError` on a dict
  missing a key; a typed Observation cannot lack a field.
- test_group_by_indicator_different_data_types: pinned that Year 2020 and "2020"
  collide but 2020.0 does not, an artifact of the f-string group key.
"""

from sspi.scoring import Observation, group_observations


def obs(code, country, year, value=100.0, unit="Index", **provenance):
    return Observation(code, country, year, value, unit, provenance)


def test_group_single_country_single_year():
    result = group_observations(
        [obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200)],
        "TEST_INDICATOR",
    )
    assert len(result) == 1
    group = result[0]
    assert group.indicator_code == "TEST_INDICATOR"
    assert group.country_code == "USA"
    assert group.year == 2020
    assert len(group.inputs) == 2
    assert group.inputs[0].dataset_code == "DATASET_A"
    assert group.inputs[1].dataset_code == "DATASET_B"
    assert group.computed == ()


def test_group_multiple_countries():
    result = group_observations(
        [
            obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200),
            obs("DATASET_A", "CAN", 2020, 150), obs("DATASET_B", "CAN", 2020, 250),
        ],
        "MULTI_COUNTRY_INDICATOR",
    )
    assert len(result) == 2
    usa = next(g for g in result if g.country_code == "USA")
    can = next(g for g in result if g.country_code == "CAN")
    assert usa.indicator_code == "MULTI_COUNTRY_INDICATOR"
    assert can.indicator_code == "MULTI_COUNTRY_INDICATOR"
    assert len(usa.inputs) == 2
    assert len(can.inputs) == 2


def test_group_multiple_years():
    result = group_observations(
        [
            obs("DATASET_A", "USA", 2019, 90), obs("DATASET_B", "USA", 2019, 190),
            obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200),
        ],
        "MULTI_YEAR_INDICATOR",
    )
    assert len(result) == 2
    g2019 = next(g for g in result if g.year == 2019)
    g2020 = next(g for g in result if g.year == 2020)
    assert g2019.country_code == "USA" and g2020.country_code == "USA"
    assert len(g2019.inputs) == 2 and len(g2020.inputs) == 2


def test_group_complex_grouping():
    observations = [
        obs(code, country, year, 1.0)
        for country in ("USA", "CAN")
        for year in (2019, 2020)
        for code in ("DATASET_A", "DATASET_B")
    ]
    result = group_observations(observations, "COMPLEX_INDICATOR")
    assert len(result) == 4
    assert {(g.country_code, g.year) for g in result} == {
        ("USA", 2019), ("USA", 2020), ("CAN", 2019), ("CAN", 2020)
    }
    assert all(len(g.inputs) == 2 for g in result)


def test_group_empty_list():
    assert group_observations([], "EMPTY_INDICATOR") == []


def test_group_single_observation():
    result = group_observations([obs("SINGLE_DATASET", "USA", 2020, 100)], "SINGLE_INDICATOR")
    assert len(result) == 1
    assert result[0].indicator_code == "SINGLE_INDICATOR"
    assert result[0].country_code == "USA"
    assert result[0].year == 2020
    assert len(result[0].inputs) == 1
    assert result[0].inputs[0].dataset_code == "SINGLE_DATASET"


def test_group_preserves_observation_fields_and_provenance():
    original = obs("DATASET_A", "USA", 2020, 100, "Index", Metadata={"source": "test"}, Notes="Test data")
    result = group_observations([original], "PRESERVE_FIELDS_INDICATOR")
    kept = result[0].inputs[0]
    assert kept is original
    assert kept.dataset_code == "DATASET_A"
    assert kept.country_code == "USA"
    assert kept.year == 2020
    assert kept.value == 100
    assert kept.unit == "Index"
    assert kept.provenance == {"Metadata": {"source": "test"}, "Notes": "Test data"}


def test_group_keeps_duplicate_observations_in_order():
    result = group_observations(
        [obs("DATASET_A", "USA", 2020, 100), obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200)],
        "DUPLICATE_INDICATOR",
    )
    assert len(result) == 1
    assert [o.dataset_code for o in result[0].inputs] == ["DATASET_A", "DATASET_A", "DATASET_B"]


def test_group_ignores_dataset_code_in_key():
    result = group_observations(
        [obs("GDP", "USA", 2020, 100), obs("POPULATION", "USA", 2020, 330), obs("UNEMPLOYMENT", "USA", 2020, 5.5)],
        "ECONOMIC_INDICATOR",
    )
    assert len(result) == 1
    assert {o.dataset_code for o in result[0].inputs} == {"GDP", "POPULATION", "UNEMPLOYMENT"}


def test_group_very_large_input():
    observations = [
        obs(code, country, year, 100)
        for country in ("USA", "CAN", "GBR", "FRA", "DEU")
        for year in (2018, 2019, 2020)
        for code in ("DATASET_A", "DATASET_B", "DATASET_C", "DATASET_D")
    ]
    result = group_observations(observations, "LARGE_INDICATOR")
    assert len(result) == 15
    assert all(len(g.inputs) == 4 for g in result)
    assert all(g.indicator_code == "LARGE_INDICATOR" for g in result)


def test_group_does_not_validate_country_code_format():
    # Domain validation of codes belongs at the ingestion boundary, not here.
    result = group_observations(
        [obs("DATASET_A", "USA", 2020), obs("DATASET_B", "EU-28", 2020), obs("DATASET_C", "XK", 2020), obs("DATASET_D", "TWN", 2020)],
        "SPECIAL_COUNTRIES_INDICATOR",
    )
    assert {g.country_code for g in result} == {"USA", "EU-28", "XK", "TWN"}


def test_group_does_not_range_check_years():
    result = group_observations(
        [obs("DATASET_A", "HIST", -100, 50), obs("DATASET_B", "HIST", -100, 60), obs("DATASET_A", "HIST", -50, 70)],
        "HISTORICAL_INDICATOR",
    )
    assert {g.year for g in result} == {-100, -50}
    assert len(next(g for g in result if g.year == -100).inputs) == 2
    assert len(next(g for g in result if g.year == -50).inputs) == 1


def test_group_key_is_a_tuple_not_a_joined_string():
    # Old code keyed on f"{CountryCode}_{Year}"; "US_A"+2020 and "USA"+2020 differ either way.
    result = group_observations(
        [obs("DATASET_A", "US_A", 2020, 100), obs("DATASET_B", "USA", 2020, 200)],
        "ID_TEST_INDICATOR",
    )
    assert len(result) == 2
    assert {g.country_code for g in result} == {"US_A", "USA"}


def test_group_order_is_first_seen():
    result = group_observations(
        [obs("A", "MYS", 2021), obs("A", "USA", 2020), obs("B", "MYS", 2021), obs("A", "USA", 2019)],
        "ORDERS",
    )
    assert [(g.country_code, g.year) for g in result] == [("MYS", 2021), ("USA", 2020), ("USA", 2019)]
