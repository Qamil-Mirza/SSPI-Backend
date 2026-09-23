"""Reference-class average: one flat mean over every observation supplied,
assigned to every requested year. Legacy semantics, legacy method name."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import REFERENCE_CLASS_AVERAGE, reference_class_average
from sspi.scoring import Observation


def obs(country, year, value, dataset="DS_A", unit="PERCENT", **prov):
    return Observation(dataset, country, year, value, unit, prov)


def test_mean_is_across_countries_and_years_together_unrestricted_by_range():
    reference = [obs("USA", 2000, 10.0), obs("USA", 2001, 20.0), obs("KEN", 2025, 60.0)]  # 2025 is outside 2000-2002 and still counts
    out = reference_class_average("AUT", "DS_A", 2000, 2002, reference)
    assert [(o.country_code, o.year, o.value) for o in out] == [("AUT", 2000, 30.0), ("AUT", 2001, 30.0), ("AUT", 2002, 30.0)]


def test_output_shape_and_provenance():
    out = reference_class_average("AUT", "UNSDG_MARINE", 2023, 2023, [obs("USA", 2010, 5.0, source_series="X")])
    (o,) = out
    assert isinstance(out, tuple)
    assert (o.dataset_code, o.country_code, o.year, o.value, o.unit) == ("UNSDG_MARINE", "AUT", 2023, 5.0, "PERCENT")
    # No source identifiers carried over: legacy built a fresh document.
    assert dict(o.provenance) == {"imputed": True, "imputation_method": REFERENCE_CLASS_AVERAGE, "reference_observation_count": 1, "requested_years": [2023, 2023]}
    assert REFERENCE_CLASS_AVERAGE == "ImputeReferenceClassAverage"


def test_requested_years_are_inclusive_and_ascending():
    out = reference_class_average("AUT", "DS_A", 2000, 2023, [obs("USA", 2000, 1.0)])
    assert [o.year for o in out] == list(range(2000, 2024))


def test_target_country_is_not_excluded_if_present_in_reference():
    out = reference_class_average("AUT", "DS_A", 2000, 2000, [obs("AUT", 2000, 100.0), obs("USA", 2000, 0.0)])
    assert out[0].value == 50.0


def test_countries_with_more_years_weigh_more():
    reference = [obs("USA", y, 0.0) for y in range(2000, 2003)] + [obs("KEN", 2000, 30.0)]
    assert reference_class_average("AUT", "DS_A", 2000, 2000, reference)[0].value == 7.5


def test_summation_follows_input_order_for_float_determinism():
    values = [0.1, 0.2, 0.3, 1e-9, 1e9]
    reference = [obs("USA", 2000 + i, v) for i, v in enumerate(values)]
    assert reference_class_average("AUT", "DS_A", 2000, 2000, reference)[0].value == sum(values) / len(values)


def test_empty_reference_is_an_error():
    with pytest.raises(ImputationError, match="empty"):
        reference_class_average("AUT", "DS_A", 2000, 2023, [])


def test_mixed_units_are_an_error():
    with pytest.raises(ImputationError, match="[Uu]nits"):
        reference_class_average("AUT", "DS_A", 2000, 2023, [obs("USA", 2000, 1.0, unit="PERCENT"), obs("KEN", 2000, 1.0, unit="KM2")])


def test_dataset_code_of_reference_is_not_checked_only_units_are():
    # Legacy only compared Unit; the output takes the dataset code the caller asked for.
    out = reference_class_average("AUT", "DS_A", 2000, 2000, [obs("USA", 2000, 1.0, dataset="OTHER")])
    assert out[0].dataset_code == "DS_A"


def test_reference_observations_are_untouched():
    reference = [obs("USA", 2000, 10.0, k="v")]
    reference_class_average("AUT", "DS_A", 2000, 2000, reference)
    assert dict(reference[0].provenance) == {"k": "v"} and reference[0].value == 10.0
