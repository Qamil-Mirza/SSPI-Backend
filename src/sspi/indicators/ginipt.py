"""GINIPT, Gini Coefficient: the executable legacy formula and impute route.

Compute route (``api/core/sspi/ms/neq/ginipt.py``): every clean
``WB_GINIPT`` row (World Bank ``SI.POV.GINI``), all years and all countries
the cleaner kept, is scored with ``goalpost(WB_GINIPT, 70, 20)``. The lower
goalpost is the larger number, so the scale is inverted: a Gini of 20 or
less scores 1, 70 or more scores 0. The goalposts were read from metadata at
runtime and are declared here so ``check_against`` verifies them. The score
unit is the legacy literal ``Coefficient``.

Impute route, reproduced by :class:`GiniptImputation`, in two stages.

1. Series fill, on the *inputs*. Each country's observed Gini series is
   carried forward to 2023, carried backward to 2000 and linearly
   interpolated across every interior gap, each step applied to the observed
   rows on their own. The filled observations are scored with the ordinary
   formula. This runs for every country in the dataset, not a country
   group, and the interpolation is not bounded by any year: a gap between
   1985 and 1992 is filled too (GINIPT-3).

2. Regression fallback, on *scores*. A country with no Gini observation at
   all (so no observed and no series-filled score) gets a predicted GINIPT
   score for every year it has an observed ISHRAT score: one pooled
   least-squares line ``GINIPT ~ ISHRAT`` is fitted on every (country, year)
   that has both an observed ISHRAT score and an observed GINIPT score, and
   the prediction is clipped to [0, 1]. The recipients come from the data,
   not from a list, and the prediction years are whatever years ISHRAT
   covers, 2024 included (GINIPT-3). These scores have no inputs; their
   provenance says how they were derived.

The second stage reads ISHRAT's persisted scores, so ISHRAT is a declared
score dependency: ``run("GINIPT")`` never runs ISHRAT and raises
``ScoreDependencyError`` when it has no scores. The legacy route had the
same order dependence, undeclared.

The legacy route cannot complete in two other situations, and neither can
this one (``ImputationError``, nothing written): no observed GINIPT score
at all (it indexed the first one for the unit), and no country lacking Gini
data (its prediction frame was empty and the pivot raised). No behaviour is
defined for either.

The fit reproduces ``sklearn.linear_model.LinearRegression`` without
scikit-learn; see ``sspi.indicators.strategy.fit_centered_least_squares``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sspi.errors import ImputationError
from sspi.imputation import extrapolate_backward, extrapolate_forward, interpolate_linear, is_imputed
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult, regression_impute_scores
from sspi.scoring import goalpost, score_indicator

WB_GINIPT = "WB_GINIPT"
FEATURE_INDICATOR = "ISHRAT"
LOWER_GOALPOST, UPPER_GOALPOST = 70, 20
UNIT = "Coefficient"  # legacy literal
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target
REGRESSION_MODEL = "GINIPT ~ ISHRAT + y_0 + e"  # legacy model string
REGRESSION_DETAILS = (  # legacy ImputationDetails, verbatim
    "ISHRAT and GINIPT both describe income inequality. Both are derived "
    "from the income distribution of a country. They are somewhat "
    "correlated: enough so that ISHRAT is a reasonable predictor of GINIPT "
    "in the absence of GINIPT data, but not so much that we feel we should "
    "only use ISHRAT data to measure income inequality. We use a simple "
    "linear regression model to predict GINIPT from ISHRAT data."
)


def score_ginipt(WB_GINIPT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_ginipt`` lambda, identical in the impute route."""
    return goalpost(WB_GINIPT, LOWER_GOALPOST, UPPER_GOALPOST)


@dataclass(frozen=True, slots=True)
class GiniptImputation:
    """The legacy ``impute_ginipt`` route as an ``ImputationStrategy``."""

    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        code, unit = context.definition.code, context.definition.unit
        observed = context.observed_scores
        if not observed:
            raise ImputationError(f"{code} cannot be imputed: there are no observed {code} scores (the legacy route fails here too). Ingest {WB_GINIPT} first.")
        rows = context.dataset(WB_GINIPT)
        start, end = SERIES_FILL_YEARS
        filled = extrapolate_forward(rows, end) + extrapolate_backward(rows, start) + interpolate_linear(rows)  # legacy order; each on the observed rows
        series = score_indicator(filled, code, score_ginipt, unit)

        covered = {s.country_code for s in observed} | {s.country_code for s in series.scored}
        features = tuple(s for s in context.dependency_scores[FEATURE_INDICATOR] if not is_imputed(s))  # legacy read the observed-score collection
        recipients = tuple(s for s in features if s.country_code not in covered)
        if not recipients:
            raise ImputationError(
                f"{code} cannot be imputed on this data: every country with an observed {FEATURE_INDICATOR} score also has Gini data, so the "
                "regression fallback has nothing to predict. The legacy route fails in this situation and no behaviour is defined for it; "
                "nothing was written."
            )
        predicted = regression_impute_scores(
            code,
            unit,
            features,
            observed,
            recipients,
            goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
            model=REGRESSION_MODEL,
            details=REGRESSION_DETAILS,
        )
        imputed = tuple(series.scored) + predicted
        filled_identities = {(s.country_code, s.year) for s in imputed}
        still_incomplete = tuple(u for u in context.observed_unscored if (u.country_code, u.year) not in filled_identities)
        return IndicatorImputationResult(imputed, still_incomplete + tuple(series.unscored))


DEFINITION = IndicatorDefinition(
    code="GINIPT",
    observed_score=score_ginipt,
    imputation=GiniptImputation(),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
    score_dependencies=(FEATURE_INDICATOR,),
)
