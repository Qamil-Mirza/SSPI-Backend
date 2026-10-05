"""ALTNRG, Alternative Energy Generation: the executable legacy formulas and
impute route.

Inputs: seven products of IEA indicator ``TESbySource`` (total energy
supply by source), in terajoules, one dataset each. The dataset names are
the legacy ones; ``IEA_GEOPWR`` ("geothermal") is the product the IEA labels
"Solar, wind and other renewables" and ``IEA_BIOWAS`` is "Biofuels and
waste" (ALTNRG-1 in docs/methodology-conflicts.md).

Compute route (``api/core/sspi/sus/nrg/altnrg.py``): a country-year is
scored only when all seven datasets have a value. The percentage

    ((NCLEAR + HYDROP + GEOPWR + BIOWAS) - 0.5 * BIOWAS)
        / (TLCOAL + NATGAS + NCLEAR + HYDROP + GEOPWR + BIOWAS + FSLOIL) * 100

is stored beside the inputs as the computed series
``IEA_ALTNRG_PERCENTAGE`` and scored with ``goalpost(percentage, 0, 60)``.
The goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. Incomplete country-years are not scored.

Impute route, on the inputs, each dataset on its own (ALTNRG-2):

1. every SSPI67 member with no row at all in a dataset gets 0.0 there for
   2000-2023. The legacy route labels these rows ``PJ`` although the data
   are in ``TJ``; reproduced;
2. every series present, of any country, is carried backward to 2000 and
   forward to 2023 and interpolated across interior gaps. The cleaner drops
   zero values, so a series that is zero until some year is carried back
   from its first non-zero value, and a series that ends (a closed nuclear
   fleet) is carried forward from its last value.

The union is scored with the same percentage and goalposts, except that a
total of zero scores 0.0, and only scores with an imputed input are kept.
The computed series is not stored on imputed scores. A country outside
SSPI67 with no row in some dataset stays unscored.
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, LEGACY_RECIPIENT_GROUP, IndicatorDefinition
from sspi.indicators.strategy import ConstantFillInputsThenScore
from sspi.scoring import ComputedSeries, goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 60
PERCENTAGE_CODE = "IEA_ALTNRG_PERCENTAGE"
PERCENTAGE_UNIT = "% of Total Energy Supply from Alternative Sources (Partial Credit for Biowaste)"  # legacy literal
ZERO_FILL_UNIT = "PJ"  # legacy literal on zero-filled rows; the source unit is TJ
ZERO_FILL_METHOD = "Zero imputation for missing energy type"  # legacy ImputationMethod string


def altnrg_percent_value(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``altnrg_percent_value``, verbatim including operation order."""
    return ((IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS) - 0.5 * IEA_BIOWAS) / (IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL) * 100


def score_altnrg_observed(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):  # noqa: N803
    """Legacy ``compute_altnrg.score_altnrg``, verbatim including operation order."""
    return goalpost(
        ((IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS) - 0.5 * IEA_BIOWAS) / (IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL) * 100,
        LOWER_GOALPOST,
        UPPER_GOALPOST,
    )


def score_altnrg_imputed(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):  # noqa: N803
    """Legacy ``impute_altnrg.score_altnrg``: the same percentage, with a zero total scored 0.0."""
    total = IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL
    if total == 0:
        return 0.0
    alt_energy = IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS - 0.5 * IEA_BIOWAS
    return goalpost((alt_energy / total) * 100, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="ALTNRG",
    observed_score=score_altnrg_observed,
    imputation=ConstantFillInputsThenScore(
        formula=score_altnrg_imputed,
        years=LEGACY_IMPUTATION_YEARS,
        recipient_group=LEGACY_RECIPIENT_GROUP,
        fill_value=0.0,
        fill_unit=ZERO_FILL_UNIT,
        fill_method=ZERO_FILL_METHOD,
    ),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
    computed_series=(ComputedSeries(PERCENTAGE_CODE, PERCENTAGE_UNIT, altnrg_percent_value),),
)
