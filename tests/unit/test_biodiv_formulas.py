"""The two legacy BIODIV formulas, kept separate on purpose.

compute route: mean of goalpost(x, 0, 100); impute route: (M + T + F) / 3 / 100.
Equal on [0, 100], not outside it."""

import pytest

from sspi.indicators.biodiv import score_biodiv_imputed, score_biodiv_observed


@pytest.mark.parametrize("marine, terrst, frshwt", [(0, 0, 0), (100, 100, 100), (36.56867346153846, 67.89465, 71.29881), (19.70109, 37.03085, 32.45402)])
def test_formulas_agree_inside_the_goalpost_range(marine, terrst, frshwt):
    assert score_biodiv_observed(marine, terrst, frshwt) == score_biodiv_imputed(marine, terrst, frshwt)


def test_observed_formula_clamps_and_imputed_formula_does_not():
    assert score_biodiv_observed(120, 100, 100) == 1.0
    assert score_biodiv_imputed(120, 100, 100) == pytest.approx(320 / 300)
    assert score_biodiv_observed(-30, 0, 0) == 0.0
    assert score_biodiv_imputed(-30, 0, 0) == pytest.approx(-0.1)


def test_legacy_summation_order_is_preserved_verbatim():
    # compute route: (frshwt + terrst + marine) / 3 ; impute route: (marine + terrst + frshwt) / 3 / 100
    m, t, f = 0.1 * 100, 0.2 * 100, 0.7 * 100
    assert score_biodiv_observed(m, t, f) == (f / 100 + t / 100 + m / 100) / 3
    assert score_biodiv_imputed(m, t, f) == (m + t + f) / 3 / 100


def test_parameter_names_are_the_dataset_codes_in_legacy_order():
    import inspect

    for fn in (score_biodiv_observed, score_biodiv_imputed):
        assert list(inspect.signature(fn).parameters) == ["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"]
