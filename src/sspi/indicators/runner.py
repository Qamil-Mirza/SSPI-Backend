"""Indicator orchestration: connect the catalogs, the repository, the
imputation layer and the scoring kernel so one indicator runs end to end.

Two layers:

* :func:`compute_indicator` is pure. Given an executable definition, the
  canonical (source-only) observations of its datasets, the canonical rows
  of any auxiliary datasets its strategy declared and the members of any
  country group it asked for, it reproduces both legacy routes:

  - the compute route: score every complete (country, year) group of
    observed rows with the observed formula, after the definition's
    ``observation_filter`` where the legacy route had one (most have none:
    no year or country filter);
  - the impute route: the definition's ``ImputationStrategy``, which
    receives the observed pass and returns the imputed scores and the groups
    still incomplete. The runner knows nothing about any indicator; the
    strategy instance carries the methodology.

  On one snapshot the two sets are disjoint, which is why one score row per
  (indicator, country, year) can hold both; the runner enforces it.

  A definition with ``imputation=None`` has no impute route: only the
  compute route runs, nothing is imputed, and missing observations stay
  unscored.

* :func:`run_indicator` reads from PostgreSQL (dependency datasets, then
  only the declared auxiliary datasets, then the group only if asked), calls
  the pure layer, and replaces the indicator's whole score set, in two short
  transactions with the computation between them. A rerun is a full refresh:
  stale imputed rows for identities that became observable disappear.

Groups still incomplete after imputation are returned in ``unscored`` and
not persisted. The legacy application persisted them to their own
collection; persisting and querying that information is deferred, not
dropped.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from sspi.errors import InvalidObservationError, ScoreDependencyError
from sspi.imputation import is_imputed
from sspi.indicators import registry as default_registry
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext
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


def _canonical(definition: IndicatorDefinition, rows: Iterable[Observation], allowed: tuple[str, ...], what: str) -> tuple[Observation, ...]:
    """Sorted canonical rows restricted to ``allowed`` datasets, refusing foreign or imputed rows."""
    order = {code: index for index, code in enumerate(allowed)}
    rows = sorted(rows, key=lambda o: (order.get(o.dataset_code, len(order)), o.country_code, o.year))
    foreign = sorted({o.dataset_code for o in rows} - set(allowed))
    if foreign:
        raise InvalidObservationError(f"compute_indicator({definition.code}) received {what} for datasets it does not consume: {foreign}")
    leaked = [(o.dataset_code, o.country_code, o.year) for o in rows if o.provenance.get("imputed", False)]
    if leaked:
        raise InvalidObservationError(f"compute_indicator({definition.code}) received imputed {what}; only canonical source observations may enter: {leaked[:5]}")
    return tuple(rows)


def _dependency_scores(definition: IndicatorDefinition, supplied: Mapping[str, Iterable[IndicatorScore]] | None) -> Mapping[str, tuple[IndicatorScore, ...]]:
    """The declared score dependencies' scores, sorted by identity; refuses
    undeclared indicators, misfiled scores and a dependency with no scores."""
    supplied = {} if supplied is None else {code: tuple(scores) for code, scores in supplied.items()}
    undeclared = sorted(set(supplied) - set(definition.score_dependencies))
    if undeclared:
        raise InvalidObservationError(f"compute_indicator({definition.code}) received scores for indicators it does not depend on: {undeclared}")
    resolved: dict[str, tuple[IndicatorScore, ...]] = {}
    for code in definition.score_dependencies:
        scores = supplied.get(code, ())
        if not scores:
            raise ScoreDependencyError(
                f"{definition.code} requires existing {code} scores for its legacy imputation procedure and none were found. "
                f"Run {code} first, then run {definition.code} again. Nothing was computed or written for {definition.code}."
            )
        misfiled = sorted({s.indicator_code for s in scores} - {code})
        if misfiled:
            raise InvalidObservationError(f"compute_indicator({definition.code}): scores supplied for dependency {code} belong to {misfiled}")
        resolved[code] = tuple(sorted(scores, key=lambda s: (s.country_code, s.year)))
    return MappingProxyType(resolved)


def compute_indicator(
    definition: IndicatorDefinition,
    observations: Iterable[Observation],
    recipients: Iterable[str] = (),
    *,
    auxiliary: Iterable[Observation] = (),
    dependency_scores: Mapping[str, Iterable[IndicatorScore]] | None = None,
) -> IndicatorRun:
    """Observed and imputed scores for one indicator from canonical observations.

    ``observations`` must belong to the definition's datasets and
    ``auxiliary`` to its strategy's auxiliary datasets; neither may contain
    imputed rows. ``recipients`` are the members of the group the strategy
    asked for; they are ignored when it asked for none.
    ``dependency_scores`` holds the existing scores of each indicator in
    ``definition.score_dependencies``, by code; a declared dependency with
    no scores raises ``ScoreDependencyError`` before anything is computed.
    Results do not depend on input order.
    """
    dependencies = _dependency_scores(definition, dependency_scores)
    observations = _canonical(definition, observations, definition.dataset_codes, "observations")
    auxiliary = _canonical(definition, auxiliary, definition.auxiliary_datasets, "auxiliary observations")
    selected = observations if definition.observation_filter is None else tuple(o for o in observations if definition.observation_filter(o))
    observed = score_indicator(selected, definition.code, definition.observed_score, definition.unit)
    if definition.imputation is None:
        return IndicatorRun(definition.code, tuple(observed.scored), (), tuple(observed.unscored))

    context = IndicatorImputationContext(
        definition=definition,
        observations=observations,
        auxiliary={code: tuple(o for o in auxiliary if o.dataset_code == code) for code in definition.auxiliary_datasets},
        observed_scores=tuple(observed.scored),
        observed_unscored=tuple(observed.unscored),
        recipients=tuple(recipients) if definition.recipient_group is not None else (),
        dependency_scores=dependencies,
    )
    result = definition.imputation.impute(context)
    not_imputed = [(s.country_code, s.year) for s in result.imputed_scores if not is_imputed(s)]
    if not_imputed:
        raise InvalidObservationError(f"{definition.code}: imputation strategy returned scores that do not classify as imputed: {not_imputed[:5]}")
    collisions = sorted({(s.country_code, s.year) for s in observed.scored} & {(s.country_code, s.year) for s in result.imputed_scores})
    if collisions:
        raise InvalidObservationError(f"{definition.code}: imputation strategy returned scores for identities the observed pass already scored: {collisions[:5]}")
    return IndicatorRun(definition.code, tuple(observed.scored), tuple(result.imputed_scores), tuple(result.unscored))


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
    datasets' observations, the strategy's auxiliary datasets and the
    persisted scores of any declared score dependencies in one transaction
    (a dependency is never run from here; if it has no scores the run stops
    with ``ScoreDependencyError`` and writes nothing); resolve the country group only if the strategy asked for
    one; compute in memory; replace the indicator's whole score set in a
    second transaction. A failure in the write leaves the previous complete
    result untouched.
    """
    from sspi.db import Repository
    from sspi.metadata import CountryCatalog, MetadataCatalog

    definition = registry.get(code)
    definition.check_against(MetadataCatalog.load() if metadata is None else metadata)
    recipients: tuple[str, ...] = ()
    if definition.recipient_group is not None:
        catalog = CountryCatalog.load() if countries is None else countries
        recipients = tuple(catalog.group(definition.recipient_group).members)

    with database.transaction() as session:
        repo = Repository(session)
        observations = repo.get_observations(dataset_codes=definition.dataset_codes)
        auxiliary = repo.get_observations(dataset_codes=definition.auxiliary_datasets) if definition.auxiliary_datasets else []
        dependency_scores = {code: repo.get_scores(indicator_codes=[code]) for code in definition.score_dependencies}

    result = compute_indicator(definition, observations, recipients, auxiliary=auxiliary, dependency_scores=dependency_scores)

    with database.transaction() as session:
        written = Repository(session).replace_indicator_scores(definition.code, result.scores)
    return replace(result, written=written)
