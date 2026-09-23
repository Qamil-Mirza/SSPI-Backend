"""Indicator orchestration: connect the catalogs, the repository, the
imputation layer and the scoring kernel so one indicator runs end to end.

Two layers:

* :func:`compute_indicator` is pure. Given an executable definition, the
  canonical (source-only) observations of its datasets and the reference
  class recipients, it reproduces both legacy routes:

  - the compute route: score every complete (country, year) group of
    observed rows with the observed formula, no year or country filter;
  - the impute route: impute each dataset in dependency order, score the
    union with the imputed formula, keep the scores that have at least one
    imputed input.

  On one snapshot the two sets are exact complements, which is why one score
  row per (indicator, country, year) can hold both.

* :func:`run_indicator` reads from PostgreSQL, calls the pure layer, and
  replaces the indicator's whole score set, in two short transactions with
  the computation between them. A rerun is a full refresh: stale imputed
  rows for identities that became observable disappear.

Groups still incomplete after imputation are returned in ``unscored`` and
not persisted. The legacy application persisted them to their own
collection; persisting and querying that information is deferred, not
dropped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

from sspi.errors import InvalidObservationError
from sspi.imputation import impute_dataset, is_imputed
from sspi.indicators import registry as default_registry
from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import IndicatorScore, Observation, UnscoredGroup, score_indicator


@dataclass(frozen=True, slots=True)
class IndicatorRun:
    """What one indicator execution produced.

    ``unscored`` holds the groups that remained incomplete after imputation.
    ``written`` is the number of score rows persisted, or ``None`` when the
    result came from :func:`compute_indicator` alone.
    """

    indicator_code: str
    observed_scores: tuple[IndicatorScore, ...]
    imputed_scores: tuple[IndicatorScore, ...]
    unscored: tuple[UnscoredGroup, ...]
    written: int | None = None

    @property
    def scores(self) -> tuple[IndicatorScore, ...]:
        return self.observed_scores + self.imputed_scores


def compute_indicator(
    definition: IndicatorDefinition,
    observations: Iterable[Observation],
    recipients: Iterable[str],
) -> IndicatorRun:
    """Observed and imputed scores for one indicator from canonical observations.

    ``observations`` must belong to the definition's datasets and must not
    themselves be imputed. ``recipients`` are the countries that receive a
    reference-class series when a dataset has no row for them at all; they
    affect nothing else. Results do not depend on input order.
    """
    codes = definition.dataset_codes
    order = {code: index for index, code in enumerate(codes)}
    observations = sorted(observations, key=lambda o: (order.get(o.dataset_code, len(order)), o.country_code, o.year))
    foreign = sorted({o.dataset_code for o in observations} - set(codes))
    if foreign:
        raise InvalidObservationError(f"compute_indicator({definition.code}) received observations for datasets it does not consume: {foreign}")
    leaked = [(o.dataset_code, o.country_code, o.year) for o in observations if o.provenance.get("imputed", False)]
    if leaked:
        raise InvalidObservationError(
            f"compute_indicator({definition.code}) received imputed observations; only canonical source observations may enter: {leaked[:5]}"
        )
    recipients = tuple(recipients)
    start_year, end_year = definition.imputation_years

    observed = score_indicator(observations, definition.code, definition.observed_score, definition.unit)

    combined: list[Observation] = []
    for code in codes:
        rows = [o for o in observations if o.dataset_code == code]
        combined.extend(impute_dataset(rows, code, recipients, start_year, end_year).combined)
    after_imputation = score_indicator(combined, definition.code, definition.imputed_score, definition.unit)
    imputed = tuple(s for s in after_imputation.scored if is_imputed(s))

    return IndicatorRun(definition.code, tuple(observed.scored), imputed, tuple(after_imputation.unscored))


def run_indicator(
    code: str,
    database: Any,
    *,
    metadata: Any | None = None,
    countries: Any | None = None,
    registry: Any = default_registry,
) -> IndicatorRun:
    """Execute one indicator against PostgreSQL and persist its score set.

    Sequence: resolve and validate the definition; read the dependency
    datasets' observations in one transaction; compute in memory; replace the
    indicator's whole score set in a second transaction. A failure in the
    write leaves the previous complete result untouched.
    """
    from sspi.db import Repository
    from sspi.metadata import CountryCatalog, MetadataCatalog

    definition = registry.get(code)
    definition.check_against(MetadataCatalog.load() if metadata is None else metadata)
    catalog = CountryCatalog.load() if countries is None else countries
    recipients = catalog.group(definition.recipient_group).members

    with database.transaction() as session:
        observations = Repository(session).get_observations(dataset_codes=definition.dataset_codes)

    result = compute_indicator(definition, observations, recipients)

    with database.transaction() as session:
        written = Repository(session).replace_indicator_scores(definition.code, result.scores)
    return replace(result, written=written)
