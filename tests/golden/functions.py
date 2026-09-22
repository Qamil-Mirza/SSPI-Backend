"""Named score, unit, and value functions shared by the golden-fixture generator
and the golden test.

This module must stay importable with no dependencies beyond the standard
library, because the generator runs it inside the OLD repository's virtualenv.
`goalpost` is injected so that the old side uses the old implementation and the
new side uses the new one; the golden test therefore compares the whole
pipeline, not just the arithmetic.
"""

from __future__ import annotations

from typing import Any, Callable


def make_functions(goalpost: Callable[[Any, Any, Any], float]) -> dict[str, dict[str, Callable]]:
    """Return {"score": {...}, "unit": {...}, "value": {...}} keyed by name."""

    # --- score functions -------------------------------------------------

    def biodiv_mean_goalpost(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        frshwt = goalpost(UNSDG_FRSHWT, 0, 100)
        terrst = goalpost(UNSDG_TERRST, 0, 100)
        marine = goalpost(UNSDG_MARINE, 0, 100)
        return (frshwt + terrst + marine) / 3

    def altnrg_score(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):
        return goalpost(
            ((IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS) - 0.5 * IEA_BIOWAS)
            / (IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL)
            * 100,
            0,
            60,
        )

    def foraid_score(TOTDON, TOTREC, POPULN, GDPMKT):
        if TOTDON > TOTREC:
            return goalpost(TOTDON * 10**8 / GDPMKT, 0, 1)
        return goalpost(TOTREC * 10**6 / POPULN, 0, 500)

    def inverted_goalpost(EPI_MSWGEN):
        return goalpost(EPI_MSWGEN, 100, 0)

    def mean_of_three_goalposts(DS_A, DS_B, DS_C):
        return (goalpost(DS_A, 0, 100) + goalpost(DS_B, 10, 90) + goalpost(DS_C, 100, 0)) / 3

    def two_dataset_average(DATASET_A, DATASET_B):
        return (DATASET_A + DATASET_B) / 2

    def uses_chained_computed(BASE_X, COMPUTED_TWICE, COMPUTED_PLUS_ONE):
        return goalpost(COMPUTED_PLUS_ONE / (BASE_X + COMPUTED_TWICE), 0, 1)

    def uses_ratio(NUMER, DENOM, COMPUTED_RATIO):
        return goalpost(COMPUTED_RATIO + NUMER / (DENOM + 1), 0, 10)

    def none_below_fifty(DATASET_A, DATASET_B):
        if DATASET_A < 50:
            return None
        return DATASET_A + DATASET_B

    def uses_maybe_text(DATASET_A, COMPUTED_MAYBE_TEXT):
        return DATASET_A + COMPUTED_MAYBE_TEXT

    def plain_sum(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    # --- unit functions --------------------------------------------------

    def foraid_unit(TOTDON, TOTREC, POPULN, GDPMKT):
        if TOTDON > TOTREC:
            return "Donor: ODA Donations (% GDP)"
        return "Recipient: ODA Received per Capita (USD per Capita)"

    def high_low_unit(DATASET_A, DATASET_B):
        return "High Score" if DATASET_A > DATASET_B else "Low Score"

    # --- value functions (computed series) --------------------------------

    def altnrg_percent(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):
        return (
            ((IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS) - 0.5 * IEA_BIOWAS)
            / (IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL)
            * 100
        )

    def twice(BASE_X):
        return BASE_X * 2

    def plus_one(COMPUTED_TWICE):
        return COMPUTED_TWICE + 1

    def ratio(NUMER, DENOM):
        return NUMER / DENOM  # raises ZeroDivisionError when DENOM == 0

    def maybe_text(DATASET_A):
        return "text" if DATASET_A > 50 else DATASET_A / 2

    return {
        "score": {
            "biodiv_mean_goalpost": biodiv_mean_goalpost,
            "altnrg_score": altnrg_score,
            "foraid_score": foraid_score,
            "inverted_goalpost": inverted_goalpost,
            "mean_of_three_goalposts": mean_of_three_goalposts,
            "two_dataset_average": two_dataset_average,
            "uses_chained_computed": uses_chained_computed,
            "uses_ratio": uses_ratio,
            "none_below_fifty": none_below_fifty,
            "uses_maybe_text": uses_maybe_text,
            "plain_sum": plain_sum,
        },
        "unit": {
            "foraid_unit": foraid_unit,
            "high_low_unit": high_low_unit,
        },
        "value": {
            "altnrg_percent": altnrg_percent,
            "twice": twice,
            "plus_one": plus_one,
            "ratio": ratio,
            "maybe_text": maybe_text,
        },
    }
