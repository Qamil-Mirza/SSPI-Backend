"""Category, pillar and SSPI scores from indicator scores.

Pure functions: no database, no pandas, no I/O. ``sspi.aggregation_runner``
reads the stored indicator scores, calls :func:`aggregate` and writes the
result.

The methodology, exactly as the legacy backend runs it
(``finalize_sspi_dynamic_score_iterator``, ``DataCoverage`` and the ``SSPI``
class in sspi-data-webapp):

1. **Which indicators count.** An indicator takes part only if every country
   in the group (SSPI67) has a score for every year of the window
   (2000-2023), observed or imputed. One missing country-year leaves it out
   of every country's scores. See :func:`select_indicators`.
2. **Pruning.** Each category keeps the indicators that take part; a category
   left with none is dropped, and so is a pillar left with no categories.
3. **Averaging.** For each country and year in the window: a category score
   is the unweighted mean of its indicators, a pillar the mean of its
   categories, the SSPI the mean of its pillars. Children are added in
   methodology order (``hierarchy.yaml``). See :func:`aggregate`.

Two things make the result bit-for-bit equal to legacy production, and an
RA changing the methodology can ignore both:

* :func:`legacy_sum` reproduces how the Python that ran legacy (3.13) adds
  floats, so results do not depend on the Python running this code.
* legacy stored a clamped score as the integer 0 or 1, and Python 3.13 adds
  integers without rounding correction; :func:`legacy_mean` therefore treats
  an indicator score of exactly 0 or 1 as such an integer.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sspi.errors import AggregationError
from sspi.metadata.models import ItemMetadata

__all__ = [
    "LEGACY_COUNTRY_GROUP",
    "LEGACY_YEARS",
    "AggregationResult",
    "Exclusion",
    "ItemScore",
    "ScoreCell",
    "aggregate",
    "legacy_mean",
    "legacy_sum",
    "select_indicators",
]

# The legacy finalizer hard-codes DataCoverage(2000, 2023, "SSPI67"). These are
# the same values as sspi.indicators.registry.LEGACY_IMPUTATION_YEARS and
# LEGACY_RECIPIENT_GROUP (a test keeps them equal); they are repeated here so
# this module does not import every indicator.
LEGACY_YEARS: tuple[int, int] = (2000, 2023)
LEGACY_COUNTRY_GROUP = "SSPI67"


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ScoreCell:
    """One stored indicator score, as the aggregation needs it."""

    indicator_code: str
    country_code: str
    year: int
    score: float | None
    imputed: bool = False


@dataclass(frozen=True, slots=True)
class ItemScore:
    """A category, pillar or SSPI score for one country and year.

    ``children`` are the codes actually averaged, in the order they were
    added (a pruned subset of the item's children in the hierarchy).
    ``indicators`` are all indicator codes underneath, in methodology order.
    """

    item_code: str
    item_type: str
    country_code: str
    year: int
    score: float
    children: tuple[str, ...]
    indicators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Exclusion:
    """Why an indicator in the hierarchy takes no part in the aggregation."""

    indicator_code: str
    missing_cells: int  # country-years of the window with no score
    first_missing: tuple[str, int]  # (country, year), the first in country then year order

    @property
    def reason(self) -> str:
        country, year = self.first_missing
        return f"{self.missing_cells} country-years without a score, first {country} {year}"


@dataclass(frozen=True, slots=True)
class AggregationResult:
    """``included`` and ``excluded`` together list every indicator in the
    hierarchy, each in methodology order. ``scores`` are ordered by country,
    then year, then SSPI, pillars and categories in methodology order."""

    included: tuple[str, ...]
    excluded: tuple[Exclusion, ...]
    scores: tuple[ItemScore, ...]


# --------------------------------------------------------------------------- #
# Arithmetic
# --------------------------------------------------------------------------- #


def legacy_sum(values: Iterable[int | float]) -> int | float:
    """``sum(values)`` exactly as CPython 3.12 and 3.13 compute it.

    Floats are added with Neumaier's compensated summation; an integer met
    after the first float is added without compensation (3.14 compensates it
    too, which can move the last bit). Leading integers are added exactly.
    """
    total: int = 0
    iterator = iter(values)
    for value in iterator:
        if isinstance(value, int):
            total += value
            continue
        high, low = total + value, 0.0
        break
    else:
        return total
    for value in iterator:
        if isinstance(value, int):
            high += float(value)
            continue
        added = high + value
        if abs(high) >= abs(value):
            low += (high - added) + value
        else:
            low += (value - added) + high
        high = added
    return high + low if low and math.isfinite(low) else high


def _as_legacy_number(score: float) -> int | float:
    """Legacy stored a clamped indicator score as the int 0 or 1."""
    return int(score) if score in (0.0, 1.0) else score


def legacy_mean(values: Sequence[float], *, indicator_scores: bool = False) -> float:
    """The unweighted mean, as legacy computes it: ``sum(values) / len(values)``.

    ``indicator_scores=True`` for a category (its children are stored
    indicator scores, see :func:`_as_legacy_number`); pillars and the SSPI
    average computed means, which are always floats.
    """
    numbers = [_as_legacy_number(v) for v in values] if indicator_scores else list(values)
    return legacy_sum(numbers) / len(numbers)


# --------------------------------------------------------------------------- #
# Step 1: which indicators take part
# --------------------------------------------------------------------------- #


def _indicator_order(hierarchy: Sequence[ItemMetadata]) -> list[str]:
    return [code for item in hierarchy if item.item_type == "Category" for code in item.children]


def select_indicators(
    hierarchy: Sequence[ItemMetadata],
    cells: Iterable[ScoreCell],
    *,
    countries: Sequence[str],
    years: tuple[int, int] = LEGACY_YEARS,
) -> tuple[tuple[str, ...], tuple[Exclusion, ...]]:
    """(included, excluded): an indicator is included when every country has a
    stored score, NULL or not, for every year of the window."""
    first, last = years
    window = range(first, last + 1)
    members = set(countries)
    present: dict[str, set[tuple[str, int]]] = {}
    for cell in cells:
        if cell.country_code in members and first <= cell.year <= last:
            present.setdefault(cell.indicator_code, set()).add((cell.country_code, cell.year))
    included: list[str] = []
    excluded: list[Exclusion] = []
    for code in _indicator_order(hierarchy):
        have = present.get(code, set())
        missing = [(c, y) for c in sorted(members) for y in window if (c, y) not in have]
        if missing:
            excluded.append(Exclusion(code, len(missing), missing[0]))
        else:
            included.append(code)
    return tuple(included), tuple(excluded)


# --------------------------------------------------------------------------- #
# Steps 2 and 3: prune and average
# --------------------------------------------------------------------------- #


def _pruned(hierarchy: Sequence[ItemMetadata], included: Sequence[str]) -> list[tuple[ItemMetadata, tuple[str, ...]]]:
    """(item, children kept) for the items that keep at least one child:
    SSPI first, then pillars, then categories, in methodology order."""
    kept_indicators = set(included)
    by_code = {item.code: item for item in hierarchy}
    categories = {
        item.code: tuple(c for c in item.children if c in kept_indicators)
        for item in hierarchy if item.item_type == "Category"
    }
    categories = {code: kids for code, kids in categories.items() if kids}
    pillars = {
        item.code: tuple(c for c in item.children if c in categories)
        for item in hierarchy if item.item_type == "Pillar"
    }
    pillars = {code: kids for code, kids in pillars.items() if kids}
    (root,) = [item for item in hierarchy if item.item_type == "SSPI"]
    pruned = [(root, tuple(p for p in root.children if p in pillars))]
    pruned += [(by_code[code], kids) for code, kids in pillars.items()]
    pruned += [(by_code[code], kids) for code, kids in categories.items()]
    return pruned


def aggregate(
    hierarchy: Sequence[ItemMetadata],
    cells: Iterable[ScoreCell],
    *,
    countries: Sequence[str],
    years: tuple[int, int] = LEGACY_YEARS,
) -> AggregationResult:
    """Category, pillar and SSPI scores for every country and year of the window.

    Raises ``AggregationError``, like legacy, when an included indicator has a
    NULL score or two scores for one country and year inside the window.
    """
    cells = list(cells)
    included, excluded = select_indicators(hierarchy, cells, countries=countries, years=years)
    if not included:
        return AggregationResult(included, excluded, ())
    first, last = years
    members = set(countries)
    taking_part = set(included)
    table: dict[tuple[str, int], dict[str, float]] = {}
    for cell in cells:
        if cell.indicator_code not in taking_part or cell.country_code not in members or not first <= cell.year <= last:
            continue
        row = table.setdefault((cell.country_code, cell.year), {})
        where = f"{cell.indicator_code} {cell.country_code} {cell.year}"
        if cell.indicator_code in row:
            raise AggregationError(f"two scores for {where}; legacy stops here too (DataMetadataMismatchError)")
        if cell.score is None:
            raise AggregationError(f"NULL score for {where}; legacy stops here too (score missing in indicator_scores)")
        row[cell.indicator_code] = cell.score

    pruned = _pruned(hierarchy, included)
    underneath = _indicators_underneath(pruned)
    scores: list[ItemScore] = []
    for country, year in sorted(table):
        row = table[(country, year)]
        values: dict[str, float] = {}
        # Categories first (they read indicator scores), then pillars, then the root.
        for item, children in reversed(pruned):
            if item.item_type == "Category":
                values[item.code] = legacy_mean([row[c] for c in children], indicator_scores=True)
            else:
                values[item.code] = legacy_mean([values[c] for c in children])
        scores += [
            ItemScore(item.code, item.item_type, country, year, values[item.code], children, underneath[item.code])
            for item, children in pruned
        ]
    return AggregationResult(included, excluded, tuple(scores))


def _indicators_underneath(pruned: list[tuple[ItemMetadata, tuple[str, ...]]]) -> dict[str, tuple[str, ...]]:
    kids = {item.code: (item.item_type, children) for item, children in pruned}
    out: dict[str, tuple[str, ...]] = {}

    def walk(code: str) -> tuple[str, ...]:
        if code not in kids:  # an indicator
            return (code,)
        if code not in out:
            out[code] = tuple(i for child in kids[code][1] for i in walk(child))
        return out[code]

    for code in kids:
        walk(code)
    return out
