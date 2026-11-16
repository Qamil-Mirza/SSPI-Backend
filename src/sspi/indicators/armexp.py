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

Production precedence (project owner, 2026-11-09, ARMEXP-5): the
registered imputation is the legacy impute route, :data:`LEGACY_IMPUTATION`,
which production ran: on production's clean rows it reproduces every stored
ARMEXP score exactly. The observed-only treatment approved on 2026-10-26 is
withdrawn. Where a hard-coded country has observed rows (the United Arab
Emirates, in the current SIPRI data), the route refuses the whole
imputation, as legacy did: ``run("ARMEXP")`` raises ``ImputationError`` and
writes nothing. ARMEXP-2 (what to do then) stays unresolved.
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


# The legacy impute route, exactly; registered (production precedence, ARMEXP-5).
LEGACY_IMPUTATION = SeriesFillThenScore(score_armexp, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS, listed_recipients=LISTED_RECIPIENTS)

DEFINITION = IndicatorDefinition(
    code="ARMEXP",
    observed_score=score_armexp,
    imputation=LEGACY_IMPUTATION,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
