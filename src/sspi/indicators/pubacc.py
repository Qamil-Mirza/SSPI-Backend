"""PUBACC, Public Access: the executable legacy formula.

The dataset is World Bank WDI indicator ``FX.OWN.TOTL.ZS``, "Account
ownership at a financial institution or with a mobile-money-service
provider (% of population ages 15+)", from the Global Findex survey: the
share of adults who report having an account, alone or with someone else,
at a bank or another financial institution, or who personally used a
mobile-money service in the past 12 months. It is not a count of bank
branches, a credit measure or a composite inclusion index.

The legacy compute route (``api/core/sspi/ms/fin/pubacc.py``) scores every
clean ``WB_PUBACC`` row, all years and all countries, with
``goalpost(WB_PUBACC, lg, ug)``, where ``lg, ug`` were read from the
methodology metadata at runtime and are (0, 100): no adult with an account
scores 0, every adult scores 1. They are declared on the definition so
``check_against`` verifies them. The score unit is the legacy literal
``Percent``.

Legacy PUBACC has no impute route. Findex is a survey run in waves (2011,
2014, 2017, 2021 and 2024, with 2022 fieldwork for a few countries), and a
country is scored only in the years the survey published a value; nothing
is interpolated between waves (PUBACC-1).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 100
UNIT = "Percent"  # legacy compute-route literal


def score_pubacc(WB_PUBACC):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_pubacc`` lambda, with the metadata goalposts."""
    return goalpost(WB_PUBACC, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="PUBACC",
    observed_score=score_pubacc,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
