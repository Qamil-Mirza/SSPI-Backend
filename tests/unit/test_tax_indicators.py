"""TAXREV and TXRDST definitions against the catalog, and the parts of their
legacy formulas that the fixtures exercise only at a few points. No
database, no network."""

import math

import pytest

from sspi.indicators import compute_indicator, registry, taxrev, txrdst
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

CATALOG = MetadataCatalog.load()


def test_definitions_agree_with_the_catalog():
    for code in ("TAXREV", "TXRDST"):
        registry.get(code).check_against(CATALOG)
    assert registry.get("TAXREV").imputation == SeriesFillThenScore(taxrev.score_taxrev, (2000, 2023), listed_recipients=("VNM", "NGA", "VEN", "DZA"))
    assert registry.get("TXRDST").imputation is None and registry.get("TXRDST").score_dependencies == ()


def test_taxrev_goalposts_are_clamped():
    assert [taxrev.score_taxrev(v) for v in (-5, 0, 10, 50, 638.7)] == [0.0, 0.0, 0.2, 1.0, 1.0]


def test_txrdst_is_the_percentage_change_of_the_share_ratio():
    # pre-tax ratio 0.15 / 0.45 = 1/3, post-tax 0.2 / 0.4 = 1/2: +50 %, scored (50 + 10) / 110
    assert math.isclose(txrdst.score_txrdst(0.2, 0.4, 0.15, 0.45), 60 / 110)
    assert txrdst.score_txrdst(0.15, 0.45, 0.15, 0.45) == 10 / 110  # no change
    assert txrdst.score_txrdst(0.1, 0.45, 0.15, 0.45) == 0.0 and txrdst.score_txrdst(0.4, 0.3, 0.15, 0.45) == 1.0


def test_txrdst_zero_pretax_ratio_scores_as_no_change_and_a_zero_top_share_raises(caplog):
    assert txrdst.score_txrdst(0.2, 0.35, 0.0, 0.45) == 10 / 110
    assert "Pretax ratio is zero" in caplog.text
    with pytest.raises(ZeroDivisionError):
        txrdst.score_txrdst(0.2, 0.0, 0.15, 0.45)  # the post-tax ratio is computed before the zero check, as in legacy
    with pytest.raises(ZeroDivisionError):
        txrdst.score_txrdst(0.2, 0.35, 0.15, 0.0)


def test_txrdst_binds_inputs_by_dataset_code_not_position():
    shares = {"WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50": 0.2, "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100": 0.4, "WID_NINCSH_PRETAX_P0P50": 0.15, "WID_NINCSH_PRETAX_P90P100": 0.45}
    observations = [Observation(code, "MYS", 2020, value, "share", {}) for code, value in reversed(list(shares.items()))]
    (score,) = compute_indicator(registry.get("TXRDST"), observations).scores
    assert math.isclose(score.score, 60 / 110) and score.unit == txrdst.UNIT
    assert compute_indicator(registry.get("TXRDST"), observations[1:]).unscored[0].details == ("WID_NINCSH_PRETAX_P90P100",)  # the first of the reversed list
