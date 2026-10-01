"""WATMAN, Water Management: the executable legacy formula and impute route.

Compute route (``api/core/sspi/sus/lnd/watman.py``): every (country, year)
with both ``UNSDG_CWUEFF`` (percent change in water-use efficiency from the
2000-2005 mean, derived in ``sspi.ingestion.derived``) and ``UNSDG_WTSTRS``
(level of water stress) is scored ``(goalpost(CWUEFF, -20, 50) +
goalpost(WTSTRS, 100, 0)) / 2``. Water stress is inverted by goalpost order.
No year or country filter.

Impute route, reproduced by :class:`WatmanImputation`:

* CWUEFF and WTSTRS are extrapolated backward to 2000 and forward to 2023.
  No interpolation.
* For a literal list of twelve countries a synthetic CWUEFF series is built
  from the auxiliary ``UNSDG_WUSEFF`` series: extrapolate it to 2000-2023,
  interpolate, then apply the same 2000-2005 baseline-change transform, this
  time emitting the baseline years too.
* Singapore receives the mean of every canonical CWUEFF value (all countries
  and years) for 2000-2023, in legacy unconditionally. Singapore now reports
  a 2005 value, so a canonical CWUEFF series exists for it and the literal
  legacy route crashes on duplicate rows. Adopted policy (WATMAN-3, decided
  2026-10-01, methodology review still open): canonical CWUEFF takes
  precedence; the reference-class series is created only when no canonical
  CWUEFF row exists for the recipient. On the data the legacy route was
  written against the two behaviours coincide.
* The union is scored with the same formula and the scores with at least
  one imputed input are kept (legacy ``filter_imputations``).

Open questions, in docs/methodology-conflicts.md: WATMAN-1 (goalposts),
WATMAN-2 (hard-coded recipients, undocumented synthetic method), WATMAN-3
(the Singapore policy above). A listed synthetic-series country that later
gains canonical CWUEFF would collide the same way; no policy exists for that
yet, so the strategy raises rather than choosing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sspi.errors import ImputationError
from sspi.imputation import extrapolate_backward, extrapolate_forward, interpolate_linear, is_imputed, reference_class_average
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult
from sspi.scoring import Observation, goalpost, score_indicator

CWUEFF, WTSTRS, WUSEFF = "UNSDG_CWUEFF", "UNSDG_WTSTRS", "UNSDG_WUSEFF"
IMPUTATION_YEARS = (2000, 2023)
BASELINE_YEARS = (2000, 2005)
# Literal lists from the legacy route, not a rule (WATMAN-2).
SYNTHETIC_CWUEFF_RECIPIENTS = ("AUS", "BGD", "CAN", "CHE", "CHL", "DEU", "ISL", "LVA", "PER", "PHL", "SVN", "THA")
REFERENCE_CLASS_RECIPIENTS = ("SGP",)
SYNTHETIC_METHOD = "Synthetic CWUEFF from WUSEFF extrapolation"  # legacy ImputationMethod string
SYNTHETIC_UNIT = "Percent"  # legacy literal; equals the canonical UNSDG_CWUEFF unit


def score_watman(UNSDG_CWUEFF, UNSDG_WTSTRS):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_watman``, identical in both routes."""
    return (goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2


def _extrapolated(rows: Iterable[Observation]) -> tuple[Observation, ...]:
    """Legacy chain: observed rows, plus backward extrapolation to 2000, plus forward to 2023."""
    rows = tuple(rows)
    rows += extrapolate_backward(rows, IMPUTATION_YEARS[0])
    rows += extrapolate_forward(rows, IMPUTATION_YEARS[1])
    return rows


def synthetic_cwueff(country_code: str, wuseff_rows: Iterable[Observation]) -> tuple[Observation, ...]:
    """Legacy ``create_synthetic_cwueff``: extend the country's WUSEFF series
    over 2000-2023 (backward, forward, then interpolate), take the mean of its
    2000-2005 values as the baseline, and emit the percent change from that
    baseline for every extended year (0 when the baseline is 0). Every row is
    imputed with the legacy method name. Nothing is emitted for a country
    whose extended series has no 2000-2005 value."""
    extended = _extrapolated(wuseff_rows)
    extended += interpolate_linear(extended)
    extended = tuple(o for o in extended if o.country_code == country_code)
    baseline_values = [o.value for o in extended if BASELINE_YEARS[0] <= o.year <= BASELINE_YEARS[1]]
    if not baseline_values:
        return ()
    baseline = sum(baseline_values) / len(baseline_values)
    first_year_after_baseline = BASELINE_YEARS[1] + 1
    in_baseline = [o for o in extended if BASELINE_YEARS[0] <= o.year <= BASELINE_YEARS[1]]
    after: dict[int, Observation] = {o.year: o for o in extended if o.year >= first_year_after_baseline}  # legacy dict: last wins
    rows: list[Observation] = []
    for source in [*in_baseline, *after.values()]:
        change = ((source.value - baseline) / baseline) * 100 if baseline != 0 else 0
        provenance = {
            "imputed": True,
            "imputation_method": SYNTHETIC_METHOD,
            "derived_from": WUSEFF,
            "baseline_years": list(BASELINE_YEARS),
            "baseline_value": baseline,
            "baseline_observation_count": len(baseline_values),
            "source_value": source.value,
            "source_unit": source.unit,
            "source_imputed": bool(source.provenance.get("imputed", False)),
            "source_imputation_method": source.provenance.get("imputation_method"),
        }
        rows.append(Observation(CWUEFF, country_code, source.year, float(change), SYNTHETIC_UNIT, provenance))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class WatmanImputation:
    """The legacy ``impute_watman`` route as an ``ImputationStrategy``."""

    auxiliary_datasets: tuple[str, ...] = (WUSEFF,)
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        cwueff = context.dataset(CWUEFF)
        wtstrs = context.dataset(WTSTRS)
        wuseff = context.auxiliary[WUSEFF]

        imputed_cwueff = _extrapolated(cwueff)
        imputed_wtstrs = _extrapolated(wtstrs)
        synthetic: list[Observation] = []
        for country in SYNTHETIC_CWUEFF_RECIPIENTS:
            rows = [o for o in wuseff if o.country_code == country]
            if rows:
                synthetic.extend(synthetic_cwueff(country, rows))
        canonical_countries = {o.country_code for o in cwueff}
        reference: list[Observation] = []
        for country in REFERENCE_CLASS_RECIPIENTS:
            if country in canonical_countries:
                continue  # canonical-first policy, WATMAN-3: the legacy route would duplicate and fail here
            reference.extend(reference_class_average(country, CWUEFF, *IMPUTATION_YEARS, cwueff))

        all_cwueff = [*imputed_cwueff, *synthetic, *reference]
        colliding = sorted({(o.country_code, o.year) for o in synthetic} & {(o.country_code, o.year) for o in imputed_cwueff})
        if colliding:
            raise ImputationError(
                f"WATMAN: the legacy impute route builds synthetic CWUEFF series for {sorted({c for c, _ in colliding})} unconditionally, but the "
                f"source now provides CWUEFF for them ({len(colliding)} colliding country-years, first {colliding[:3]}); the legacy route "
                "fails on this data too and no policy has been decided for synthetic recipients. See WATMAN-3 in docs/methodology-conflicts.md."
            )
        scored = score_indicator([*imputed_wtstrs, *all_cwueff], context.definition.code, score_watman, context.definition.unit)
        return IndicatorImputationResult(tuple(s for s in scored.scored if is_imputed(s)), tuple(scored.unscored))


DEFINITION = IndicatorDefinition(
    code="WATMAN",
    observed_score=score_watman,
    imputation=WatmanImputation(),
    unit="Index",
)
