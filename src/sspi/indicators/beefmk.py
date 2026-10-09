"""BEEFMK, Beef Market: the executable legacy formula and impute route.

Inputs: ``UNFAO_BFPROD``, FAOSTAT Food Balances (domain FBS) item 2731
"Bovine Meat", element "Production", in thousand tonnes; ``UNFAO_BFCONS``,
the same item's "Food supply quantity (kg/capita/yr)", labelled
``kg/capita/year``; and ``WB_POPULN``, World Bank total population.

Compute route (``api/core/sspi/sus/ghg/beefmk.py``): a country-year is
scored only when all three have a value. The score is the mean of two
goalposted parts, each with the goalposts hard-coded in the route as
(50, 0), less being better:

    (goalpost(UNFAO_BFPROD / WB_POPULN, 50, 0) + goalpost(UNFAO_BFCONS, 50, 0)) / 2

Production is divided by population as stored, thousand tonnes per person,
a number of the order of 1e-5, so the production part is within a millionth
of 1.0 for every country (BEEFMK-1). No year filter.

Impute route: each country's earliest observed *score* is carried back to
2000 and its latest forward to 2023 (no interpolation); then Singapore, the
one country hard-coded in the route ("From coverage report, SGP has no
observations"), gets for every year 2000-2023 the flat mean of every
observed score of every other country, all years. The list is applied
whatever the data hold; if Singapore ever has an observed score the run
stops (see :class:`~sspi.indicators.strategy.ExtrapolateScores`).
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, IndicatorDefinition
from sspi.indicators.strategy import ExtrapolateScores
from sspi.scoring import goalpost

PRODUCTION_GOALPOSTS = (50, 0)  # legacy `prod_lg, prod_ug = 50, 0`
CONSUMPTION_GOALPOSTS = (50, 0)  # legacy `cons_lg, cons_ug = 50, 0`
REFERENCE_CLASS_RECIPIENTS = ("SGP",)  # legacy `countries_no_data = ["SGP"]`


def score_beefmk(UNFAO_BFPROD, UNFAO_BFCONS, WB_POPULN):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_beefmk.score_beefmk``, verbatim including operation order."""
    prod_per_cap = UNFAO_BFPROD / WB_POPULN
    score_prod = goalpost(prod_per_cap, *PRODUCTION_GOALPOSTS)
    score_cons = goalpost(UNFAO_BFCONS, *CONSUMPTION_GOALPOSTS)
    return (score_prod + score_cons) / 2


DEFINITION = IndicatorDefinition(
    code="BEEFMK",
    observed_score=score_beefmk,
    imputation=ExtrapolateScores(
        forward_to=LEGACY_IMPUTATION_YEARS[1],
        backward_to=LEGACY_IMPUTATION_YEARS[0],
        listed_recipients=REFERENCE_CLASS_RECIPIENTS,
        reference_years=LEGACY_IMPUTATION_YEARS,
    ),
    unit="Index",
    goalposts=PRODUCTION_GOALPOSTS,  # metadata's single pair; both parts use it
)
