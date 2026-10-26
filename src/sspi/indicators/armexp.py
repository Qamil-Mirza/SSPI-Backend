"""ARMEXP, Arms Transfers: the executable legacy formula and impute route.

The dataset is the SIPRI Arms Transfers Database "Exports by" table of
delivered major conventional weapons, 1990-2025 (``SIPRI_ARMEXP``,
:mod:`sspi.ingestion.sipri`), in millions of SIPRI trend-indicator values
(TIV). The TIV measures the VOLUME of transfers from a unit production cost
per weapon type; it is not a price paid, and SIPRI says it should not be
read as the financial value of the transfers. A country appears only if it
exported in some year of the window; an empty cell (no delivery found) is
missing, a published ``0`` (under 0.5 million TIV) is kept.

Compute route (``api/core/sspi/pg/glb/armexp.py``): every clean row, all
years and all countries, is scored with ``goalpost(SIPRI_ARMEXP, 500, 0)``:
no exports scores 1, 500 million TIV or more scores 0. The goalposts were
read from metadata at runtime and are declared here so ``check_against``
verifies them. The score unit is the legacy literal ``Expenditure`` in both
routes, although the input is a volume (ARMEXP-1).

Impute route, in the legacy order: each exporter's series is carried
forward to 2023 and backward to 2000 and interpolated across every interior
gap, each step from the observed rows on their own; then the United Arab
Emirates, Bangladesh and Iraq each get, for every year 2000-2023, the flat
mean of every observed row (all exporters, all years: ARMEXP-2). The
filled values are scored with the same formula. If a hard-coded country has
observed rows, legacy held two values for one country-year and refused the
whole imputation, after deleting the stored ARMEXP imputations. The United
Arab Emirates exports in the current SIPRI data, so on today's data the
legacy backend stored the compute route's scores and no imputed score
(ARMEXP-2, executed on the original answer).

Approved execution treatment (project owner, 2026-10-26, following FDEPTH):
the registered definition is observed-only. ``run("ARMEXP")`` scores every
observation with the legacy formula and attempts no imputation, so a live
run succeeds and stores what the legacy backend stored on today's data. No
imputed score is stored, and a missing country-year is neither filled nor
scored as zero. The legacy impute route is kept, unregistered, as
:data:`LEGACY_IMPUTATION`: the golden tests require it to reproduce the
legacy route exactly on collision-free data and to refuse a collision as
legacy did. Registered in ``OBSERVED_ONLY_EXECUTIONS``
(``tests/golden/parity.py``); ARMEXP-2 stays scientifically unresolved.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 500, 0
UNIT = "Expenditure"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)
SERIES_FILL_STEPS = ("forward", "backward", "interpolate")  # the legacy route's order
LISTED_RECIPIENTS = ("ARE", "BGD", "IRQ")  # impute_reference_class_average calls, in order


def score_armexp(SIPRI_ARMEXP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_armexp`` lambda, identical in the impute route."""
    return goalpost(SIPRI_ARMEXP, LOWER_GOALPOST, UPPER_GOALPOST)


# The legacy impute route, exactly; not registered (approved observed-only treatment, ARMEXP-2).
LEGACY_IMPUTATION = SeriesFillThenScore(score_armexp, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS, listed_recipients=LISTED_RECIPIENTS)

DEFINITION = IndicatorDefinition(
    code="ARMEXP",
    observed_score=score_armexp,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
