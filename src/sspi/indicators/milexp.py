"""MILEXP, Military Expenditure: the executable legacy formula and impute
route, prepared but NOT REGISTERED (MILEXP-5).

The dataset is SIPRI's military expenditure as a share of GDP
(``SIPRI_MILEXP``), read from SIPRI's revised workbook, the approved single
source (MILEXP-4; :func:`sspi.ingestion.sipri.normalize_milex_workbook`),
with the approved year, name and unit corrections (MILEXP-1, MILEXP-2).

Compute route (``api/core/sspi/pg/glb/milexp.py``): every clean row, all
years, is scored with ``goalpost(SIPRI_MILEXP, 5, 0)``: no military spending
scores 1, 5% of GDP or more scores 0 (the 2018 scores used 10 → 0:
MILEXP-3). Score unit ``%``, in both routes.

Impute route, in the legacy order: each country's series is carried forward
to 2023 and backward to 2000 and interpolated, each step from the observed
rows; then Iceland gets the value 0 for every year 2000-2023, with the unit
of the first clean row (``clean_milexp[0]["Unit"]``) and method
``ImputeDatasetValue`` (MILEXP-3). An empty dataset has no first row: legacy
failed, and so does this definition. An Icelandic observation meets the
fixed zero: legacy then either refused the imputation (where its own fills
collided with the fixed rows) or, as on the revised workbook, which
publishes 0 for Iceland in every year, stored an imputed score beside each
observed one. No precedence has been decided (MILEXP-5), so this definition
raises there, and it is not registered.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 5, 0
UNIT = "%"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)
SERIES_FILL_STEPS = ("forward", "backward", "interpolate")  # the legacy route's order
LISTED_CONSTANTS = (("ISL", 0),)  # impute_dataset_value("ISL", 2000, 2023, "SIPRI_MILEXP", 0, clean_milexp[0]["Unit"])


def score_milexp(SIPRI_MILEXP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_milexp`` lambda, identical in the impute route."""
    return goalpost(SIPRI_MILEXP, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="MILEXP",
    observed_score=score_milexp,
    imputation=SeriesFillThenScore(score_milexp, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS, listed_constants=LISTED_CONSTANTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
