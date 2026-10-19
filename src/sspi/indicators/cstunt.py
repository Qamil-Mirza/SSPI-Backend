"""CSTUNT, Child Stunting: the executable legacy formula and impute route.

Compute route (``api/core/sspi/pg/hlc/cstunt.py``): every clean
``UNSDG_CSTUNT`` row (UN SDG indicator 2.2.1, series ``SH_STA_STNT``, both
sexes, ages under 5: the proportion of children under 5 moderately or
severely stunted, in percent), all years and all countries the cleaner kept,
is scored with ``goalpost(UNSDG_CSTUNT, 50, 0)``. The lower goalpost is the
larger number, so the scale is inverted: a prevalence of 0 scores 1, 50 or
more scores 0. The score unit is the legacy literal ``%``.

Impute route, reproduced by :class:`CstuntImputation`, in two stages.

1. Series fill, on the *inputs*. Each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated across
   every interior gap, each step applied to the observed rows on their own,
   and the filled observations are scored with the ordinary formula. The
   legacy route labelled these scores ``Coefficient`` (CSTUNT-1). Every
   country in the dataset is treated, not a country group.

2. Regression fallback, on *scores*. A country with no CSTUNT observation at
   all gets a predicted score for every year it has a World Bank GDP per
   capita value (``WB_GDP_PERCAP_CURPRICE_USD``, current US dollars). The
   GDP value is first put on a score scale with ``goalpost(GDP, 0, 100000)``
   (so 100,000 dollars or more is 1); one pooled least-squares line
   ``CSTUNT ~ GDP score`` is fitted on every (country, year) with both a GDP
   score and an observed CSTUNT score, and the prediction is clipped to
   [0, 1]. The recipients come from the data, not from a list, and the
   prediction years are whatever years the GDP series covers, 1960 to the
   latest (CSTUNT-2). These scores carry the observed scores' unit ``%``,
   have no inputs, and say how they were derived in their provenance.

The legacy route cannot complete when there is no observed CSTUNT score (it
indexed the first one for the unit), when no GDP row was ingested, or when
every country with GDP data also has CSTUNT data (its prediction frame was
empty); neither can this one (``ImputationError``, nothing written).

The fit is the one GINIPT uses, reproducing
``sklearn.linear_model.LinearRegression`` without scikit-learn; see
``sspi.indicators.strategy.fit_centered_least_squares``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from sspi.errors import ImputationError
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult, SeriesFillThenScore, regression_impute_scores
from sspi.scoring import IndicatorScore, goalpost

GDP_PER_CAPITA = "WB_GDP_PERCAP_CURPRICE_USD"
LOWER_GOALPOST, UPPER_GOALPOST = 50, 0
GDP_GOALPOSTS = (0, 100000)  # legacy: obs["Score"] = goalpost(obs["Value"], 0, 100000)
UNIT = "%"  # legacy literal of the compute route; the regression reuses the first observed score's unit
SERIES_FILL_UNIT = "Coefficient"  # legacy literal of the impute route's series-filled scores
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target
REGRESSION_MODEL = "CSTUNT ~ WB_GDP_PERCAP_CURPRICE_USD + y_0 + e"  # legacy model string
REGRESSION_DETAILS = "WB_GDP_PERCAP_CURPRICE_USD is a predictor of the prevalence of Child Stunting"  # legacy ImputationDetails, verbatim


def score_cstunt(UNSDG_CSTUNT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_cstunt`` lambda, identical in the impute route."""
    return goalpost(UNSDG_CSTUNT, LOWER_GOALPOST, UPPER_GOALPOST)


def gdp_feature_scores(rows) -> tuple[IndicatorScore, ...]:
    """The legacy feature documents: each GDP per capita row with
    ``Score = goalpost(Value, 0, 100000)`` and ``FeatureCode`` the dataset
    code, which the regression keys on as it keys on an indicator code."""
    lower, upper = GDP_GOALPOSTS
    return tuple(
        IndicatorScore(GDP_PER_CAPITA, o.country_code, o.year, goalpost(o.value, lower, upper), o.unit, (o,), ())
        for o in rows
    )


@dataclass(frozen=True, slots=True)
class CstuntImputation:
    """The legacy ``impute_cstunt`` route as an ``ImputationStrategy``."""

    auxiliary_datasets: tuple[str, ...] = (GDP_PER_CAPITA,)
    recipient_group: str | None = None
    series_fill: SeriesFillThenScore = field(default_factory=lambda: SeriesFillThenScore(score_cstunt, SERIES_FILL_YEARS, unit=SERIES_FILL_UNIT))

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        code = context.definition.code
        observed = context.observed_scores
        if not observed:
            raise ImputationError(f"{code} cannot be imputed: there are no observed {code} scores (the legacy route fails here too). Ingest UNSDG_CSTUNT first.")
        series = self.series_fill.impute(context)  # legacy order: forward, backward, interpolation, each on the observed rows

        gdp = context.auxiliary.get(GDP_PER_CAPITA, ())
        if not gdp:
            raise ImputationError(f"{code} cannot be imputed: no {GDP_PER_CAPITA} observations, the predictor of the regression fallback (the legacy route fails here too). Ingest {GDP_PER_CAPITA}.")
        covered = {s.country_code for s in observed} | {s.country_code for s in series.imputed_scores}
        features = gdp_feature_scores(gdp)
        recipients = tuple(s for s in features if s.country_code not in covered)
        if not recipients:
            raise ImputationError(
                f"{code} cannot be imputed on this data: every country with {GDP_PER_CAPITA} data also has CSTUNT data, so the regression "
                "fallback has nothing to predict. The legacy route fails in this situation and no behaviour is defined for it; nothing was written."
            )
        predicted = regression_impute_scores(
            code,
            observed[0].unit,  # legacy: unit = clean_cstunt[0]["Unit"]
            features,
            observed,
            recipients,
            goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
            model=REGRESSION_MODEL,
            details=REGRESSION_DETAILS,
        )
        lower, upper = GDP_GOALPOSTS
        feature_transform = f"goalpost({GDP_PER_CAPITA}, {lower}, {upper})"
        predicted = tuple(dataclasses.replace(s, provenance={**s.provenance, "feature_transform": feature_transform}) for s in predicted)
        return IndicatorImputationResult(series.imputed_scores + predicted, series.unscored)


DEFINITION = IndicatorDefinition(
    code="CSTUNT",
    observed_score=score_cstunt,
    imputation=CstuntImputation(),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
