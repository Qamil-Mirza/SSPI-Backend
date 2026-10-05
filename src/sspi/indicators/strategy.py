"""Indicator-level imputation strategies: how an indicator produces its
imputed scores after the observed scoring pass.

This is orchestration owned by the indicator layer. It is distinct from
``sspi.imputation``, which imputes *observations* (series extrapolation,
interpolation, reference-class means) and whose result type is
``sspi.imputation.ImputationResult``. A strategy decides which of those
primitives to apply, to which countries, and how to turn the outcome into
``IndicatorScore`` rows; its result type is :class:`IndicatorImputationResult`.

Two kinds of strategy exist. Input-level ones impute observations and score
them with the ordinary formula (BIODIV, WATMAN, CARBON, EMPLOY, COLBAR,
ALTNRG). Score-level ones
derive new ``IndicatorScore`` rows from the observed scores themselves
(DEFRST: forward extrapolation of scores, reference-class mean of scores;
NRGINT and AIRPOL: :class:`ExtrapolateScores`); the primitives for that are
:func:`extrapolate_scores_forward`, :func:`extrapolate_scores_backward` and
:func:`reference_class_average_scores`, and such a score says how it was
derived in its own ``provenance`` rather than in its inputs.

A third shape reads another indicator's scores (GINIPT: a regression of its
observed scores on ISHRAT scores predicts a score where it has no data).
The definition declares those indicators as ``score_dependencies`` and the
context carries their persisted scores; :func:`regression_impute_scores` is
the primitive.

Every strategy is pure Python: no database, no network, no catalog access.
The generic runner supplies everything a strategy declares it needs
(:attr:`ImputationStrategy.auxiliary_datasets`,
:attr:`ImputationStrategy.recipient_group`, and the definition's
``score_dependencies``) and calls :meth:`impute` once.
Indicator-specific behaviour, including any hard-coded recipient list the
legacy route had, lives in the strategy instance, never in the runner.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sspi.errors import ImputationError
from sspi.imputation import BACKWARD_EXTRAPOLATION, FORWARD_EXTRAPOLATION, REFERENCE_CLASS_AVERAGE, extrapolate_backward, extrapolate_forward, impute_dataset, interpolate_linear, is_imputed
from sspi.scoring import IndicatorScore, Observation, UnscoredGroup, score_indicator

if TYPE_CHECKING:
    from sspi.indicators.registry import IndicatorDefinition


@dataclass(frozen=True, slots=True)
class IndicatorImputationContext:
    """Everything a strategy may look at."""

    definition: IndicatorDefinition
    observations: tuple[Observation, ...]  # canonical rows of definition.dataset_codes
    auxiliary: Mapping[str, tuple[Observation, ...]]  # canonical rows of strategy.auxiliary_datasets, by code
    observed_scores: tuple[IndicatorScore, ...]  # the observed pass
    observed_unscored: tuple[UnscoredGroup, ...]
    recipients: tuple[str, ...]  # members of strategy.recipient_group, else ()
    dependency_scores: Mapping[str, tuple[IndicatorScore, ...]] = field(default_factory=lambda: MappingProxyType({}))  # persisted scores of definition.score_dependencies, by indicator code

    def dataset(self, code: str) -> tuple[Observation, ...]:
        """Canonical rows of one dependency dataset, in input order."""
        return tuple(o for o in self.observations if o.dataset_code == code)


@dataclass(frozen=True, slots=True)
class IndicatorImputationResult:
    """What a strategy produced. Every score must classify as imputed."""

    imputed_scores: tuple[IndicatorScore, ...]
    unscored: tuple[UnscoredGroup, ...]  # groups still incomplete after imputation


@runtime_checkable
class ImputationStrategy(Protocol):
    """An indicator's executable imputation methodology."""

    @property
    def auxiliary_datasets(self) -> tuple[str, ...]: ...

    @property
    def recipient_group(self) -> str | None: ...

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult: ...


# --------------------------------------------------------------------------- #
# Score-level primitives (the legacy helpers applied to indicator documents)
# --------------------------------------------------------------------------- #


def _score_series(scores: Iterable[IndicatorScore]) -> list[list[IndicatorScore]]:
    """Each country's scores in year order, countries in first-seen order; a repeated identity is an error."""
    by_country: dict[str, list[IndicatorScore]] = {}
    for score in scores:
        by_country.setdefault(score.country_code, []).append(score)
    for series in by_country.values():
        series.sort(key=lambda s: s.year)
        for earlier, later in zip(series, series[1:]):
            if earlier.year == later.year:
                raise ImputationError(f"duplicate score identity {earlier.indicator_code}/{earlier.country_code}/{earlier.year} in extrapolation input")
    return list(by_country.values())


def _extrapolated(anchor: IndicatorScore, year: int, method: str) -> IndicatorScore:
    provenance = {"imputed": True, "imputation_method": method, "imputation_distance": abs(year - anchor.year), "source_year": anchor.year}
    return IndicatorScore(anchor.indicator_code, anchor.country_code, year, anchor.score, anchor.unit, anchor.inputs, anchor.computed, provenance)


def extrapolate_scores_forward(scores: Iterable[IndicatorScore], end_year: int) -> tuple[IndicatorScore, ...]:
    """Legacy ``extrapolate_forward`` on indicator documents: per country,
    carry the latest score forward to ``end_year``. The legacy helper
    deep-copied the latest document, so each new score keeps that year's
    inputs and computed values; its own provenance says it is imputed, by
    forward extrapolation, from ``source_year``, at ``imputation_distance``."""
    return tuple(_extrapolated(series[-1], year, FORWARD_EXTRAPOLATION) for series in _score_series(scores) for year in range(series[-1].year + 1, end_year + 1))


def extrapolate_scores_backward(scores: Iterable[IndicatorScore], start_year: int) -> tuple[IndicatorScore, ...]:
    """Legacy ``extrapolate_backward`` on indicator documents: per country,
    carry the earliest score back to ``start_year``. The mirror image of
    :func:`extrapolate_scores_forward`, with the same provenance fields."""
    return tuple(_extrapolated(series[0], year, BACKWARD_EXTRAPOLATION) for series in _score_series(scores) for year in range(start_year, series[0].year))


def reference_class_average_scores(country_code: str, indicator_code: str, start_year: int, end_year: int, reference: Iterable[IndicatorScore]) -> tuple[IndicatorScore, ...]:
    """Legacy ``impute_reference_class_average(..., "Indicator", ...)``: one
    flat mean of every reference score, assigned to each year of the range.
    The reference is used exactly as supplied; only units are checked. The
    imputed scores have no inputs; their provenance says how many scores
    the mean came from."""
    reference = list(reference)
    if not reference:
        raise ImputationError(f"reference scores for {indicator_code}/{country_code} are empty")
    unit = reference[0].unit
    if any(s.unit != unit for s in reference):
        raise ImputationError(f"units are not consistent across reference scores for {indicator_code}: {sorted({s.unit for s in reference})}")
    mean = sum(s.score for s in reference) / len(reference)
    provenance = {"imputed": True, "imputation_method": REFERENCE_CLASS_AVERAGE, "reference_score_count": len(reference), "requested_years": [start_year, end_year]}
    return tuple(IndicatorScore(indicator_code, country_code, year, mean, unit, (), (), provenance) for year in range(start_year, end_year + 1))


# --------------------------------------------------------------------------- #
# Shared strategies
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ImputeInputsThenScore:
    """The legacy impute-route shape shared by BIODIV: for each dependency
    dataset, extrapolate backward to ``years[0]``, forward to ``years[1]``,
    interpolate, and give every ``recipient_group`` member with no rows at
    all the reference-class mean; score the union with ``formula``; keep the
    scores that have at least one imputed input (legacy
    ``filter_imputations``)."""

    formula: Callable[..., Any]
    years: tuple[int, int]
    recipient_group: str
    auxiliary_datasets: tuple[str, ...] = ()

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        start, end = self.years
        combined: list[Observation] = []
        for code in context.definition.dataset_codes:
            combined.extend(impute_dataset(context.dataset(code), code, context.recipients, start, end).combined)
        scored = score_indicator(combined, context.definition.code, self.formula, context.definition.unit)
        return IndicatorImputationResult(tuple(s for s in scored.scored if is_imputed(s)), tuple(scored.unscored))


@dataclass(frozen=True, slots=True)
class ConstantFillInputsThenScore:
    """The legacy impute-route shape of ALTNRG. For each dependency dataset
    on its own:

    1. every ``recipient_group`` member with no row at all in that dataset
       gets ``fill_value`` for each year of ``years``, with unit
       ``fill_unit`` and method ``fill_method`` (the legacy literals);
    2. every series that is present, of any country, is carried backward to
       ``years[0]`` and forward to ``years[1]`` and interpolated across
       interior gaps, each step from the observed rows.

    The observed and imputed rows of all datasets are then scored together
    with ``formula``, and the scores with at least one imputed input are
    kept (legacy ``filter_imputations``). Recipients are found from the
    data. The interpolation is not bounded by ``years``."""

    formula: Callable[..., Any]
    years: tuple[int, int]
    recipient_group: str
    fill_value: float
    fill_unit: str
    fill_method: str
    auxiliary_datasets: tuple[str, ...] = ()

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        start, end = self.years
        combined: list[Observation] = list(context.observations)
        for code in context.definition.dataset_codes:
            rows = context.dataset(code)
            present = {o.country_code for o in rows}
            for country in context.recipients:
                if country not in present:
                    provenance = {"imputed": True, "imputation_method": self.fill_method}
                    combined.extend(Observation(code, country, year, self.fill_value, self.fill_unit, provenance) for year in range(start, end + 1))
            combined.extend(extrapolate_backward(rows, start) + extrapolate_forward(rows, end) + interpolate_linear(rows))  # legacy order
        scored = score_indicator(combined, context.definition.code, self.formula, context.definition.unit)
        return IndicatorImputationResult(tuple(s for s in scored.scored if is_imputed(s)), tuple(scored.unscored))


@dataclass(frozen=True, slots=True)
class SeriesFillThenScore:
    """The legacy impute-route shape of a one-dataset indicator with no
    reference class (EMPLOY, COLBAR): carry each country's observed series
    forward to ``years[1]`` and backward to ``years[0]``, interpolate every
    interior gap, each step applied to the observed rows on their own, and
    score the filled observations with ``formula``. Every country in the
    dataset is treated; a country with no observation gets nothing. The
    interpolation is not bounded by ``years``.

    ``unit`` is the unit literal the legacy impute route wrote on its
    scores where that differs from the compute route's; ``None`` uses the
    definition's unit."""

    formula: Callable[..., Any]
    years: tuple[int, int]
    unit: str | None = None
    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        start, end = self.years
        filled: list[Observation] = []
        for code in context.definition.dataset_codes:
            rows = context.dataset(code)
            filled.extend(extrapolate_forward(rows, end) + extrapolate_backward(rows, start) + interpolate_linear(rows))  # legacy order
        scored = score_indicator(filled, context.definition.code, self.formula, context.definition.unit if self.unit is None else self.unit)
        return IndicatorImputationResult(tuple(scored.scored), tuple(scored.unscored))


@dataclass(frozen=True, slots=True)
class ExtrapolateScores:
    """The legacy impute-route shape that fills *scores*, not inputs (NRGINT,
    AIRPOL): each country's earliest observed score is carried back to
    ``backward_to`` (where given) and its latest observed score forward to
    ``forward_to``. Interior gaps are not filled. Every country with an
    observed score is treated.

    With a ``recipient_group``, each member of the group that has no
    observed score at all then receives, for every year of
    ``reference_years``, the flat mean of all observed scores (legacy
    ``impute_reference_class_average`` with ``item_type="Indicator"``). The
    recipients are found from the data, as in the legacy route; no list is
    hard-coded, so an observed and an imputed score can never share an
    identity."""

    forward_to: int
    backward_to: int | None = None
    recipient_group: str | None = None
    reference_years: tuple[int, int] | None = None
    auxiliary_datasets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.recipient_group is None) != (self.reference_years is None):
            raise ImputationError("ExtrapolateScores: recipient_group and reference_years go together; give both or neither")

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        observed = context.observed_scores
        imputed: list[IndicatorScore] = []
        if self.backward_to is not None:
            imputed.extend(extrapolate_scores_backward(observed, self.backward_to))
        imputed.extend(extrapolate_scores_forward(observed, self.forward_to))  # legacy order: backward, forward, reference class
        if self.reference_years is not None and observed:  # legacy: `if ref_data:`
            scored_countries = {s.country_code for s in observed}
            for country in context.recipients:
                if country not in scored_countries:
                    imputed.extend(reference_class_average_scores(country, context.definition.code, *self.reference_years, observed))
        filled = {(s.country_code, s.year) for s in imputed}
        return IndicatorImputationResult(tuple(imputed), tuple(u for u in context.observed_unscored if (u.country_code, u.year) not in filled))


# --------------------------------------------------------------------------- #
# Cross-indicator regression (legacy ``utilities.regression_imputation``)
# --------------------------------------------------------------------------- #

REGRESSION_IMPUTATION = "RegressionImputation"  # legacy ImputationMethod string


def fit_centered_least_squares(x: Iterable[float], y: Iterable[float]) -> tuple[float, float]:
    """(coefficient, intercept) of ``y ~ x`` fitted the way the legacy
    ``sklearn.linear_model.LinearRegression(fit_intercept=True)`` fitted one
    feature: subtract the means, solve the centered least-squares problem
    with LAPACK ``gelsd``, recover the intercept from the means. The same
    steps in the same order, so the legacy coefficients are reproduced
    without scikit-learn (the textbook covariance/variance ratio differs in
    the last bits). Inputs must already be in training order."""
    import numpy as np  # deferred: the registry and strategies import without numpy

    features = np.asarray(list(x), dtype=float).reshape(-1, 1)
    targets = np.asarray(list(y), dtype=float)
    if features.shape[0] == 0 or features.shape[0] != targets.shape[0]:
        raise ImputationError(f"regression needs equally many feature and target values and at least one; got {features.shape[0]} and {targets.shape[0]}")
    feature_offset = np.average(features, axis=0)
    target_offset = np.average(targets, axis=0)
    coefficients, *_ = np.linalg.lstsq(features - feature_offset, targets - target_offset, rcond=None)
    intercept = target_offset - np.dot(feature_offset, coefficients)
    return float(coefficients[0]), float(intercept)


def regression_impute_scores(
    indicator_code: str,
    unit: str,
    feature_scores: Iterable[IndicatorScore],
    outcome_scores: Iterable[IndicatorScore],
    prediction_scores: Iterable[IndicatorScore],
    *,
    goalposts: tuple[float, float],
    model: str,
    details: str | None = None,
) -> tuple[IndicatorScore, ...]:
    """Legacy ``regression_imputation`` with one feature indicator.

    Train on every (country, year) that has both a feature score and an
    outcome score (inner join, pooled over countries and years, ordered by
    country then year); predict a score for every identity in
    ``prediction_scores`` from its feature score; clip to [0, 1]. The
    predicted scores have no inputs: the legacy document carried none, only
    the value the score implies under ``goalposts``, kept here as
    ``implied_value``. Their provenance names the method, the feature
    indicator and score, the fitted line and the training size.

    A prediction identity that already has an outcome score is refused: the
    legacy helper would have returned the known score relabelled as imputed.
    """
    features = _numeric_by_identity(feature_scores, "feature")
    outcomes = _numeric_by_identity(outcome_scores, "outcome")
    predictions = _numeric_by_identity(prediction_scores, "prediction")
    feature_codes = sorted({s.indicator_code for s in features.values()} | {s.indicator_code for s in predictions.values()})
    if len(feature_codes) != 1:
        raise ImputationError(f"regression imputation for {indicator_code} supports exactly one feature indicator, got {feature_codes}")
    (feature_code,) = feature_codes
    training = sorted(set(features) & set(outcomes))
    if not training:
        raise ImputationError(f"regression imputation for {indicator_code}: no (country, year) has both a {feature_code} score and a {indicator_code} score to train on")
    known = sorted(set(predictions) & set(outcomes))
    if known:
        raise ImputationError(f"regression imputation for {indicator_code}: prediction identities already have observed scores: {known[:5]}")
    coefficient, intercept = fit_centered_least_squares((features[i].score for i in training), (outcomes[i].score for i in training))
    lower, upper = goalposts
    imputed: list[IndicatorScore] = []
    for country_code, year in sorted(predictions):
        feature_score = float(predictions[(country_code, year)].score)
        raw = feature_score * coefficient + intercept
        score = max(0.0, min(1.0, raw))
        provenance = {
            "imputed": True,
            "imputation_method": REGRESSION_IMPUTATION,
            "imputation_distance": 0,
            "regression_model": model,
            "feature_indicator": feature_code,
            "feature_score": feature_score,
            "coefficient": coefficient,
            "intercept": intercept,
            "raw_prediction": raw,
            "training_score_count": len(training),
            "implied_value": (upper - lower) * score + lower,
            "goalposts": [lower, upper],
        }
        if details is not None:
            provenance["imputation_details"] = details
        imputed.append(IndicatorScore(indicator_code, country_code, year, score, unit, (), (), provenance))
    return tuple(imputed)


def _numeric_by_identity(scores: Iterable[IndicatorScore], role: str) -> dict[tuple[str, int], IndicatorScore]:
    """Scores with a numeric score, by (country, year); a missing score is
    dropped, as the legacy pivot dropped it, and a duplicate identity is an error."""
    by_identity: dict[tuple[str, int], IndicatorScore] = {}
    for score in scores:
        if isinstance(score.score, bool) or not isinstance(score.score, (int, float)):
            continue
        identity = (score.country_code, score.year)
        if identity in by_identity:
            raise ImputationError(f"duplicate {role} score identity {score.indicator_code}/{score.country_code}/{score.year} in regression input")
        by_identity[identity] = score
    return by_identity
