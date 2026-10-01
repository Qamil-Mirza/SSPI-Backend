"""The parity comparison itself: exact, and specific about what differs."""

import math

import pytest

from tests.golden.parity import assert_parity


def record(country, year, score, unit="Index"):
    return {"country_code": country, "year": year, "score": score, "unit": unit}


LEGACY = [record("AUT", 2020, 0.5), record("MYS", 2020, 0.25)]


def test_identical_records_pass():
    assert_parity("x", [dict(r) for r in LEGACY], LEGACY)
    assert_parity("empty", [], [])


def test_missing_and_extra_identities_are_named():
    with pytest.raises(AssertionError) as info:
        assert_parity("X scores", [record("AUT", 2020, 0.5), record("USA", 2020, 0.1)], LEGACY)
    message = str(info.value)
    assert "X scores" in message and "in legacy but not produced: [('MYS', 2020)]" in message and "produced but not in legacy: [('USA', 2020)]" in message


def test_a_one_ulp_difference_fails_and_names_the_field():
    drifted = [record("AUT", 2020, math.nextafter(0.5, 1.0)), record("MYS", 2020, 0.25)]
    with pytest.raises(AssertionError, match=r"\('AUT', 2020\) differs in \['score'\]"):
        assert_parity("x", drifted, LEGACY)


def test_unit_difference_fails():
    with pytest.raises(AssertionError, match=r"differs in \['unit'\]"):
        assert_parity("x", [record("AUT", 2020, 0.5, "INDEX"), record("MYS", 2020, 0.25)], LEGACY)


def test_order_and_duplicates_fail():
    with pytest.raises(AssertionError, match="different order"):
        assert_parity("x", list(reversed(LEGACY)), LEGACY)
    with pytest.raises(AssertionError, match="duplicate"):
        assert_parity("x", LEGACY + [LEGACY[0]], LEGACY)
