"""COALPW, Energy From Coal: the executable legacy formulas and impute route.

Inputs: the seven ``TESbySource`` products ALTNRG reads (total energy
supply by source, terajoules, one dataset each), the same canonical
observations. The legacy route reuses the ALTNRG datasets unchanged,
including the mislabelled ``IEA_GEOPWR`` ("Solar, wind and other
renewables") and ``IEA_BIOWAS`` (ALTNRG-1).

Compute route (``api/core/sspi/sus/ghg/coalpw.py``): a country-year is
scored only when all seven datasets have a value. The coal share of the
seven-product total,

    TLCOAL / (TLCOAL + NATGAS + NCLEAR + HYDROP + GEOPWR + BIOWAS + FSLOIL)

a fraction, not a percentage, is scored with ``goalpost(share, 0.4, 0)``:
less coal is better, a share of 40 % or more scores 0. The goalposts were
read from metadata at runtime and are declared here so ``check_against``
verifies them. No computed series is stored. Incomplete country-years are
not scored.

Impute route: line for line the ALTNRG route (ALTNRG-2) on the same seven
datasets. Every SSPI67 member with no row at all in a dataset gets 0.0 there
for 2000-2023 (labelled ``PJ``, a legacy literal; the data are TJ); every
series present is carried back to 2000, forward to 2023 and interpolated.
The union is scored with the same share and goalposts, except that a total
of zero scores 1.0 (ALTNRG scores it 0.0), and only scores with an imputed
input are kept. The cleaner drops zero values, so a country that burns no
coal has no ``IEA_TLCOAL`` row: it is never scored by the compute route and
its zero-filled coal scores 1.0 as an imputed score (COALPW-1).
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, LEGACY_RECIPIENT_GROUP, IndicatorDefinition
from sspi.indicators.strategy import ConstantFillInputsThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0.4, 0
ZERO_TOTAL_SCORE = 1.0  # legacy impute route: "Perfect score for no energy consumption (or all zeros)"
ZERO_FILL_UNIT = "PJ"  # legacy literal on zero-filled rows; the source unit is TJ
ZERO_FILL_METHOD = "Zero imputation for missing energy type"  # legacy ImputationMethod string


def score_coalpw_observed(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_coalpw.score_coalpw``, verbatim including operation order."""
    IEA_TTLSUM = IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL  # noqa: N806
    return goalpost(IEA_TLCOAL / IEA_TTLSUM, LOWER_GOALPOST, UPPER_GOALPOST)


def score_coalpw_imputed(IEA_TLCOAL, IEA_NATGAS, IEA_NCLEAR, IEA_HYDROP, IEA_GEOPWR, IEA_BIOWAS, IEA_FSLOIL):  # noqa: N803
    """Legacy ``impute_coalpw.score_coalpw``: the same share, with a zero total scored 1.0."""
    IEA_TTLSUM = IEA_TLCOAL + IEA_NATGAS + IEA_NCLEAR + IEA_HYDROP + IEA_GEOPWR + IEA_BIOWAS + IEA_FSLOIL  # noqa: N806
    if IEA_TTLSUM == 0:
        return ZERO_TOTAL_SCORE
    return goalpost(IEA_TLCOAL / IEA_TTLSUM, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="COALPW",
    observed_score=score_coalpw_observed,
    imputation=ConstantFillInputsThenScore(
        formula=score_coalpw_imputed,
        years=LEGACY_IMPUTATION_YEARS,
        recipient_group=LEGACY_RECIPIENT_GROUP,
        fill_value=0.0,
        fill_unit=ZERO_FILL_UNIT,
        fill_method=ZERO_FILL_METHOD,
    ),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
