"""AQELEC, Availability and Quality of Electricity: the executable legacy
formula.

The legacy compute route (``api/core/sspi/pg/inf/aqelec.py``) groups every
clean ``WB_AVELEC`` and ``WEF_QUELEC`` row by country and year, with no
country or year filter, and scores each group holding both with::

    0.5 * goalpost(WB_AVELEC, 0, 100) + 0.5 * goalpost(WEF_QUELEC, 1, 7)

in that order of operations. Higher is better for both. A country-year with
only one input is incomplete and gets no score. The score unit is the legacy
literal ``Index``. The goalposts are hard-coded in the route (the indicator
has no metadata goalposts); the 2018 static metadata listed (0, 7) for the
quality input (AQELEC-1).

The inputs:

* ``WB_AVELEC``: World Bank WDI ``EG.ELC.ACCS.ZS``, "Access to electricity
  (% of population)". The shared World Bank cleaner drops a zero, as it
  drops every falsy value; the source has none;
* ``WEF_QUELEC``: World Economic Forum ``WEF.GCIHH.EOSQ064``, "Quality of
  electricity supply, 1-7 (best)", the Executive Opinion Survey answer to
  "In your country, how would you assess the reliability of the electricity
  supply?", from the WEF Global Competitiveness Index Historical Dataset
  workbook (``sspi.ingestion.wef``). The series covers 2007-2017 only and
  is never extended.

Legacy AQELEC has no impute route: there is no AQELEC score before 2007 or
after 2017, and none for a country without a WEF survey value.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

ACCESS_GOALPOSTS = (0, 100)
QUALITY_GOALPOSTS = (1, 7)
UNIT = "Index"  # legacy compute-route literal


def score_aqelec(WB_AVELEC, WEF_QUELEC):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_aqelec`` lambda."""
    return 0.5 * goalpost(WB_AVELEC, *ACCESS_GOALPOSTS) + 0.5 * goalpost(WEF_QUELEC, *QUALITY_GOALPOSTS)


DEFINITION = IndicatorDefinition(
    code="AQELEC",
    observed_score=score_aqelec,
    imputation=None,
    unit=UNIT,
)
