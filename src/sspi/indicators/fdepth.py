"""FDEPTH, Financial Depth: the executable legacy formula.

The legacy compute route (``api/core/sspi/ms/fin/fdepth.py``) groups every
clean ``WB_CREDIT`` and ``WB_DPOSIT`` row by country and year, with no
country or year filter, and scores each group holding both with::

    goalpost(WB_CREDIT, 0, 200) / 2 + goalpost(WB_DPOSIT, 0, 100) / 2

in that order of operations (each half divided before the sum). Higher is
better for both inputs. A country-year with only one of the two inputs is
incomplete and gets no score. The score unit is the legacy literal
``Index``. The goalposts are hard-coded in the route; the indicator-level
metadata pair (0, 200) describes only the credit input and is not read, so
no goalposts are declared on the definition (FDEPTH-2).

The inputs are two World Bank series, both percentages of GDP as published:

* ``WB_CREDIT``: WDI ``FS.AST.PRVT.GD.ZS``, "Domestic credit to private
  sector (% of GDP)";
* ``WB_DPOSIT``: Global Financial Development ``GFDD.OI.02``, "Bank deposits
  to GDP (%)", deposits in deposit money banks only, although the dataset
  is named and described as financial-system deposits (FDEPTH-3). The
  database has not been updated since September 2022 and ends in 2021, and
  it holds no United Kingdom series.

The shared World Bank cleaner drops zeros, as it drops every falsy value.

Legacy FDEPTH has an impute route, but it cannot produce anything on any
input (FDEPTH-1): it queries clean data by ``IndicatorCode`` (clean rows
carry only ``DatasetCode``), slices intermediates named ``CREDIT`` and
``DPOSIT`` out of a ``Datasets`` list that clean rows do not have, and then
raises inside the hard-coded GBR reference-class step on the empty
reference data, after deleting every stored FDEPTH imputation. The only
FDEPTH scores the legacy backend ever persisted are the compute route's,
so this definition has no imputation strategy. The golden file records the
route's failure on the fixture, on an empty dataset and on a probe written
in the route's older schema (``tests/golden/fdepth_cases.json``), and the
gate registers it in ``INOPERATIVE_IMPUTE_ROUTES``.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

CREDIT_GOALPOSTS = (0, 200)
DEPOSIT_GOALPOSTS = (0, 100)
UNIT = "Index"  # legacy compute-route literal


def score_fdepth(WB_CREDIT, WB_DPOSIT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_fdepth`` closure in ``compute_fdepth``."""
    return goalpost(WB_CREDIT, *CREDIT_GOALPOSTS) / 2 + goalpost(WB_DPOSIT, *DEPOSIT_GOALPOSTS) / 2


DEFINITION = IndicatorDefinition(
    code="FDEPTH",
    observed_score=score_fdepth,
    imputation=None,
    unit=UNIT,
)
