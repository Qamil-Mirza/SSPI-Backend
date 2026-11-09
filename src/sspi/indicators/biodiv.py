"""BIODIV, Biodiversity Protection: the two executable legacy formulas.

The legacy application scored BIODIV with two different functions, one in
the compute route and one in the impute route (``api/core/sspi/sus/eco/
biodiv.py``). They agree for inputs inside [0, 100], which is every value the
UN source has produced, and differ outside it. Both are kept verbatim,
including summation order, because collapsing them would be a methodology
decision. The canonical metadata's ``score_function`` text describes the
compute-route one.

Production precedence (project owner decision 2026-11-09, BIODIV-6): the
registered imputation is the route production serves, the one legacy
replaced on 2025-11-25 (commit fccc5c13b, "BIODIV Imputation Logic
Corrected"), not the pinned commit's. It differs from the pinned route only
for a hard-coded list of nine countries (the legacy comment: "Countries with
no observations"): each gets, for every year 2000-2023 and for ALL THREE
components, the mean of every clean row of that component from the other
countries, so their own terrestrial and freshwater rows are not used and the
score is one constant. Every other series is extrapolated and interpolated
exactly as in the pinned route, and no other country receives a reference
value. Parity is with production itself (tests/golden/production). The
pinned commit's route stays here, unregistered and parity-tested, as
``PINNED_IMPUTATION``.

The other methodology questions (BIODIV-2 to BIODIV-5) are open; BIODIV-1 is
superseded by BIODIV-6. See docs/methodology-conflicts.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sspi.errors import ImputationError
from sspi.imputation import extrapolate_backward, extrapolate_forward, interpolate_linear, is_imputed, reference_class_average
from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, LEGACY_RECIPIENT_GROUP, IndicatorDefinition
from sspi.indicators.strategy import ImputeInputsThenScore, IndicatorImputationContext, IndicatorImputationResult
from sspi.scoring import Observation, goalpost, score_indicator


def score_biodiv_observed(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_biodiv.score_biodiv``: mean of goalpost(x, 0, 100)."""
    frshwt = goalpost(UNSDG_FRSHWT, 0, 100)
    terrst = goalpost(UNSDG_TERRST, 0, 100)
    marine = goalpost(UNSDG_MARINE, 0, 100)
    return (frshwt + terrst + marine) / 3


def score_biodiv_imputed(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):  # noqa: N803
    """Legacy ``impute_biodiv.score_biodiv``: (M + T + F) / 3 / 100, unclamped."""
    return (UNSDG_MARINE + UNSDG_TERRST + UNSDG_FRSHWT) / 3 / 100


# The pinned commit's impute route (76f842b0): each dataset extrapolated to
# 2000-2023 and interpolated, SSPI67 members with no rows given the
# reference-class mean, scored with the impute-route formula, imputed rows
# kept. Not registered (production precedence, BIODIV-6); kept for parity.
PINNED_IMPUTATION = ImputeInputsThenScore(formula=score_biodiv_imputed, years=LEGACY_IMPUTATION_YEARS, recipient_group=LEGACY_RECIPIENT_GROUP)

# The legacy route's hard-coded list, verbatim and in its order (fccc5c13b^:
# api/core/sspi/sus/eco/biodiv.py, countries_no_data).
PRODUCTION_REFERENCE_COUNTRIES = ("CHE", "SVK", "HUN", "ETH", "SGP", "AUT", "LUX", "KWT", "CZE")


@dataclass(frozen=True, slots=True)
class ProductionBiodivImputation:
    """The BIODIV impute route production serves (legacy before fccc5c13b).

    For each component dataset: every series is extrapolated backward to
    ``years[0]``, forward to ``years[1]`` and interpolated, as in the pinned
    route. Then each country of ``reference_countries`` loses all its rows of
    that component, observed or extrapolated, and gets the mean of every
    observed row of the component from the countries NOT in the list (all
    years) for each year of ``years``. The union is scored with ``formula``
    and the scores with at least one imputed input are kept.

    A listed country with an observed BIODIV score in ``years`` would be
    scored twice (legacy stored both); no precedence has been decided, so
    that raises ``ImputationError`` and nothing is written. Observed scores
    outside ``years`` collide with nothing and are kept.
    """

    formula: Callable[..., Any]
    years: tuple[int, int]
    reference_countries: tuple[str, ...]
    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        listed = set(self.reference_countries)
        start, end = self.years
        collisions = sorted({(s.country_code, s.year) for s in context.observed_scores if s.country_code in listed and start <= s.year <= end})
        if collisions:
            raise ImputationError(
                f"{context.definition.code}: {len(collisions)} observed scores belong to countries the production imputation "
                f"replaces with reference-class means (first: {collisions[:3]}). The source now has complete data the "
                "hard-coded list did not expect; production would store an observed and an imputed score for the same "
                "country and year. No precedence is decided (BIODIV-6): methodology review required. Nothing was written."
            )
        combined: list[Observation] = []
        for code in context.definition.dataset_codes:
            observed = context.dataset(code)
            backward = extrapolate_backward(observed, start)
            forward = extrapolate_forward(observed + backward, end)
            interpolated = interpolate_linear(observed + backward + forward)
            combined.extend(o for o in observed + backward + forward + interpolated if o.country_code not in listed)
            reference = tuple(o for o in observed if o.country_code not in listed)
            for country in self.reference_countries:
                combined.extend(reference_class_average(country, code, start, end, reference))
        scored = score_indicator(combined, context.definition.code, self.formula, context.definition.unit)
        return IndicatorImputationResult(tuple(s for s in scored.scored if is_imputed(s)), tuple(scored.unscored))


IMPUTATION = ProductionBiodivImputation(formula=score_biodiv_imputed, years=LEGACY_IMPUTATION_YEARS, reference_countries=PRODUCTION_REFERENCE_COUNTRIES)

DEFINITION = IndicatorDefinition(
    code="BIODIV",
    observed_score=score_biodiv_observed,
    imputation=IMPUTATION,
    unit="Index",
)
