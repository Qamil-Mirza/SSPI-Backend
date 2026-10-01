"""BIODIV, Biodiversity Protection: the two executable legacy formulas.

The legacy application scored BIODIV with two different functions, one in
the compute route and one in the impute route (``api/core/sspi/sus/eco/
biodiv.py``). They agree for inputs inside [0, 100], which is every value the
UN source has produced, and differ outside it. Both are kept verbatim,
including summation order, because collapsing them would be a methodology
decision. The canonical metadata's ``score_function`` text describes the
compute-route one.

Documented, unresolved methodology conflict: the retired 2018 static
metadata says landlocked countries omit the marine component and average two;
the methodology text says average three; the executable route fills a
missing marine series from the reference class and averages three. This
module implements the executable behaviour and nothing landlocked-specific.

Open questions: BIODIV-1 to BIODIV-5 in docs/methodology-conflicts.md.
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, LEGACY_RECIPIENT_GROUP, IndicatorDefinition
from sspi.indicators.strategy import ImputeInputsThenScore
from sspi.scoring import goalpost


def score_biodiv_observed(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_biodiv.score_biodiv``: mean of goalpost(x, 0, 100)."""
    frshwt = goalpost(UNSDG_FRSHWT, 0, 100)
    terrst = goalpost(UNSDG_TERRST, 0, 100)
    marine = goalpost(UNSDG_MARINE, 0, 100)
    return (frshwt + terrst + marine) / 3


def score_biodiv_imputed(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):  # noqa: N803
    """Legacy ``impute_biodiv.score_biodiv``: (M + T + F) / 3 / 100, unclamped."""
    return (UNSDG_MARINE + UNSDG_TERRST + UNSDG_FRSHWT) / 3 / 100


# The legacy impute route: each dataset extrapolated to 2000-2023 and
# interpolated, SSPI67 members with no rows given the reference-class mean,
# scored with the impute-route formula, imputed rows kept.
IMPUTATION = ImputeInputsThenScore(formula=score_biodiv_imputed, years=LEGACY_IMPUTATION_YEARS, recipient_group=LEGACY_RECIPIENT_GROUP)

DEFINITION = IndicatorDefinition(
    code="BIODIV",
    observed_score=score_biodiv_observed,
    imputation=IMPUTATION,
    unit="Index",
)
