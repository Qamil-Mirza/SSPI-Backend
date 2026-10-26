"""RDFUND, Research and Development: the executable legacy formula and impute
route.

The datasets are two UN SDG series, each one row per area with no
disaggregation: ``UNSDG_RDPGDP`` = ``GB_XPD_RSDV`` (indicator 9.5.1, research
and development expenditure as a proportion of GDP, unit ``PERCENT``) and
``UNSDG_NRSRCH`` = ``GB_POP_SCIERD`` (indicator 9.5.2, researchers in
full-time equivalent per million inhabitants, unit ``PER_1000000_POP``).

Compute route (``api/core/sspi/pg/glb/rdfund.py``): every country-year with
both datasets is scored with the mean of ``goalpost(UNSDG_RDPGDP, 0, 4)`` and
``goalpost(UNSDG_NRSRCH, 0, 5000)``, unit ``Index``; a country-year with one
of them is incomplete. No year filter.

Impute route: each dataset on its own keeps its observed rows and adds each
series carried forward to 2023, backward to 2000 and interpolated; then
Bangladesh gets the flat mean of every observed ``UNSDG_RDPGDP`` row for
2000-2023, and Peru, Bangladesh and Israel get the flat mean of every
observed ``UNSDG_NRSRCH`` row for 2000-2023 (RDFUND-1). Everything is scored
together and the scores with at least one imputed input are kept, so an
imputed RDFUND score can pair an observed value of one dataset with a
carried or reference value of the other (RDFUND-2). A hard-coded country
with observed rows of its dataset makes the legacy route refuse the whole
imputation; here it raises ``ImputationError``.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillInputsThenScore
from sspi.scoring import goalpost

RDPGDP_GOALPOSTS = (0, 4)
NRSRCH_GOALPOSTS = (0, 5000)
UNIT = "Index"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)
SERIES_FILL_STEPS = ("forward", "backward", "interpolate")  # the legacy route's order, per dataset
LISTED_RECIPIENTS = (("UNSDG_NRSRCH", ("PER", "BGD", "ISR")), ("UNSDG_RDPGDP", ("BGD",)))  # the legacy route's order


def score_rdfund(UNSDG_RDPGDP, UNSDG_NRSRCH):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_rdfund`` closure, identical in both routes."""
    unsdg_edurdp_score = goalpost(UNSDG_RDPGDP, *RDPGDP_GOALPOSTS)
    unsdg_nrsrch_score = goalpost(UNSDG_NRSRCH, *NRSRCH_GOALPOSTS)
    return (unsdg_edurdp_score + unsdg_nrsrch_score) / 2


DEFINITION = IndicatorDefinition(
    code="RDFUND",
    observed_score=score_rdfund,
    imputation=SeriesFillInputsThenScore(score_rdfund, SERIES_FILL_YEARS, listed_recipients=LISTED_RECIPIENTS, steps=SERIES_FILL_STEPS),
    unit=UNIT,
)
