"""Run the aggregation against the database: ``run_aggregation(database)``.

Reads the stored indicator scores, computes category, pillar and SSPI scores
with ``sspi.aggregation.aggregate`` and replaces the ``item_score`` table, all
in one transaction: a failure leaves the previous table untouched (legacy
emptied ``sspi_item_data`` first and could leave it empty or half-filled).

Aggregation never runs an indicator. Run the indicators first
(``SSPI().run(code)``); rerunning an indicator afterwards makes the stored
aggregates stale until the next ``run_aggregation``, and
``SSPI().query(items=...)`` warns about it.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass

from sspi.aggregation import LEGACY_COUNTRY_GROUP, LEGACY_YEARS, Exclusion, aggregate
from sspi.db import Database, Repository
from sspi.metadata import CountryCatalog, MetadataCatalog

__all__ = ["AggregationRun", "run_aggregation"]

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AggregationRun:
    """What one run did. ``included`` + ``excluded`` list every indicator in the
    hierarchy; check ``excluded`` after changing an indicator or its imputation,
    because one missing country-year removes an indicator from every score."""

    included: tuple[str, ...]
    excluded: tuple[Exclusion, ...]
    scores_written: int
    by_type: dict[str, int]
    countries: tuple[str, ...]
    years: tuple[int, int]

    def report(self) -> str:
        lines = [
            f"{self.scores_written} scores written ({', '.join(f'{n} {t}' for t, n in self.by_type.items()) or 'none'}) "
            f"for {len(self.countries)} countries, {self.years[0]}-{self.years[1]}",
            f"{len(self.included)} indicators included: {', '.join(self.included) or 'none'}",
            f"{len(self.excluded)} indicators excluded:",
        ]
        lines += [f"  {e.indicator_code}: {e.reason}" for e in self.excluded]
        return "\n".join(lines)


def run_aggregation(
    database: Database,
    *,
    metadata: MetadataCatalog | None = None,
    countries: CountryCatalog | None = None,
    country_group: str = LEGACY_COUNTRY_GROUP,
    years: tuple[int, int] = LEGACY_YEARS,
) -> AggregationRun:
    """Aggregate the stored indicator scores and replace every stored category,
    pillar and SSPI score. Raises ``AggregationError`` (and writes nothing)
    where legacy would stop: a NULL score of an included indicator."""
    metadata = metadata or MetadataCatalog.load()
    countries = countries or CountryCatalog.load()
    members = countries.group(country_group).members
    with database.transaction() as session:
        repo = Repository(session)
        cells = repo.get_score_cells(countries=members, years=years)
        result = aggregate(metadata.hierarchy(), cells, countries=members, years=years)
        written = repo.replace_item_scores(result.scores)
    by_type = Counter(s.item_type for s in result.scores)
    run = AggregationRun(
        included=result.included,
        excluded=result.excluded,
        scores_written=written,
        by_type={t: by_type[t] for t in ("SSPI", "Pillar", "Category") if by_type[t]},
        countries=tuple(members),
        years=years,
    )
    log.info("aggregation run:\n%s", run.report())
    return run
