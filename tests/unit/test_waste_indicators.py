"""The executable Waste category: its identity (MSWGEN, RECYCL, STCONS; not
EWASTE), the MSWGEN formula and goalposts, and the status of each member.
Pure, no database, no network."""

import pytest

from sspi.errors import NotIngestibleError, SourceUnavailableError, UnknownCodeError
from sspi.indicators import registry
from sspi.indicators.mswgen import score_mswgen
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.ingestion.runner import resolve_datasets
from sspi.metadata import MetadataCatalog
from sspi.scoring import goalpost

WASTE = ("MSWGEN", "RECYCL", "STCONS")


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def test_waste_is_exactly_mswgen_recycl_and_stcons(catalog):
    assert tuple(i.code for i in catalog.indicators() if i.category_code == "WST") == WASTE
    assert {catalog.indicator(c).pillar_code for c in WASTE} == {"SUS"}


def test_ewaste_is_not_a_current_indicator(catalog):
    with pytest.raises(UnknownCodeError):
        catalog.indicator("EWASTE")
    with pytest.raises(UnknownCodeError):
        registry.get("EWASTE")
    assert not any("EWASTE" in d.code for d in catalog.datasets())


def test_only_mswgen_is_executable():
    assert [c for c in WASTE if c in registry.codes()] == ["MSWGEN"]
    for code in ("RECYCL", "STCONS"):
        with pytest.raises(UnknownCodeError, match="no executable definition"):
            registry.get(code)


def test_mswgen_definition_agrees_with_metadata(catalog):
    definition = registry.get("MSWGEN")
    definition.check_against(catalog)
    assert definition.dataset_codes == ("EPI_MSWGEN",) and definition.goalposts == (100, 0) and definition.unit == "Index"
    assert definition.imputation is None and definition.score_dependencies == () and definition.auxiliary_datasets == ()
    assert catalog.dataset("EPI_MSWGEN").unit == "Index"  # an EPI score, not kg/capita/year as the description says (MSWGEN-1)


def test_mswgen_is_one_minus_the_epi_score_over_one_hundred():
    assert score_mswgen(13.3) == goalpost(13.3, 100, 0) and score_mswgen(64.2) < score_mswgen(13.3)
    assert score_mswgen(0.0) == 1.0 and score_mswgen(100.0) == 0.0  # a reported zero is a valid (worst) EPI score
    assert score_mswgen(120.0) == 0.0 and score_mswgen(-5.0) == 1.0  # clamped


def test_waste_inputs_are_not_ingestible(catalog):
    with pytest.raises(SourceUnavailableError, match="no WPC series") as info:
        resolve_datasets(["EPI_MSWGEN"], catalog)
    assert isinstance(info.value, NotIngestibleError)
    assert set(UNAVAILABLE_SOURCES) == {"EPI_MSWGEN"}
    for code in ("WB_RECYCL", "FPI_ECOFPT_PER_CAP", "WID_CARBON_TOT_P0P100", "WID_CARBON_TOT_P90P100"):
        assert code not in SUPPORTED_DATASETS
        with pytest.raises(NotIngestibleError, match="no ingestion path") as info:
            resolve_datasets([code], catalog)
        assert not isinstance(info.value, SourceUnavailableError)
