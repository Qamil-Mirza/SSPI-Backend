"""CHMPOL: canonical metadata, ingestion of its five datasets through the
generic UNSDG path, the formula, the registry entry and no-imputation
behaviour. No database, no network."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from sspi.indicators import IndicatorDefinition, compute_indicator, registry
from sspi.indicators.chmpol import DEFINITION, score_chmpol
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "unsdg" / "12_4_1_sample.json").read_text())
DATASETS = ("UNSDG_STKHLM", "UNSDG_MINMAT", "UNSDG_MONTRL", "UNSDG_BASELA", "UNSDG_ROTDAM")
SERIES = {
    "UNSDG_STKHLM": "SG_HAZ_CMRSTHOLM",
    "UNSDG_MINMAT": "SG_HAZ_CMRMNMT",
    "UNSDG_MONTRL": "SG_HAZ_CMRMNTRL",
    "UNSDG_BASELA": "SG_HAZ_CMRBASEL",
    "UNSDG_ROTDAM": "SG_HAZ_CMRSTHOLM",  # legacy mapping, CHMPOL-1
}


class FakeClient:
    def __init__(self):
        self.fetched = []

    def fetch_indicator(self, code):
        self.fetched.append(code)
        return {"12.4.1": FIXTURE["data"]}[code]


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


@pytest.fixture(scope="module")
def normalized(metadata):
    results, _ = fetch_and_normalize(resolve_datasets(list(DATASETS), metadata), FakeClient(), metadata=metadata)
    return {dataset.code: result for dataset, result in results}


def obs(dataset, country, year, value):
    return Observation(dataset, country, year, value, "PERCENT")


def full(country, year, values):
    return [obs(d, country, year, v) for d, v in zip(DATASETS, values)]


def test_canonical_source_metadata(metadata):
    for code in DATASETS:
        dataset = metadata.dataset(code)
        assert (dataset.source.organization_code, dataset.source.query_code, dataset.unit) == ("UNSDG", "12.4.1", "PERCENT")
        assert dataset.source.organization_series_code == SERIES[code]
        assert dataset.source.dimensions is None
    assert "CHMPOL-1" in metadata.dataset("UNSDG_ROTDAM").source.note
    assert metadata.indicator("CHMPOL").dataset_codes == ("UNSDG_STKHLM", "UNSDG_BASELA", "UNSDG_MONTRL", "UNSDG_MINMAT", "UNSDG_ROTDAM")
    assert (metadata.indicator("CHMPOL").pillar_code, metadata.indicator("CHMPOL").category_code) == ("SUS", "LND")


def test_the_corrections_are_recorded_in_provenance():
    import yaml

    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    edits = {(e["file"], e["field"]): e for e in provenance["edits"]}
    for code in DATASETS:
        edit = edits[(f"datasets/{code}.yaml", "source.organization_series_code")]
        assert (edit["old"], edit["new"]) == ("12.4.1", SERIES[code])
    assert "CHMPOL-1" in edits[("datasets/UNSDG_ROTDAM.yaml", "source.organization_series_code")]["reason"]


def test_five_datasets_share_one_fetch(metadata):
    client = FakeClient()
    results, fetches = fetch_and_normalize(resolve_datasets(list(DATASETS), metadata), client, metadata=metadata)
    assert client.fetched == ["12.4.1"] == list(fetches) and [d.code for d, _ in results] == list(DATASETS)


def test_rotdam_reproduces_the_legacy_stockholm_mapping(normalized):
    stockholm = [(o.country_code, o.year, o.value) for o in normalized["UNSDG_STKHLM"].observations]
    rotterdam = [(o.country_code, o.year, o.value) for o in normalized["UNSDG_ROTDAM"].observations]
    assert stockholm == rotterdam and len(rotterdam) == 15
    assert {o.provenance["source_series"] for o in normalized["UNSDG_ROTDAM"].observations} == {"SG_HAZ_CMRSTHOLM"}
    assert any(row["series"] == "SG_HAZ_CMRROTDAM" for row in FIXTURE["data"])  # the source does publish Rotterdam data


def test_normalized_values_and_coverage(normalized):
    years = {code: sorted({o.year for o in r.observations}) for code, r in normalized.items()}
    assert years["UNSDG_MINMAT"] == [2020, 2025] and all(years[c] == [2015, 2020, 2025] for c in DATASETS if c != "UNSDG_MINMAT")
    values = {(o.dataset_code, o.country_code, o.year): o.value for r in normalized.values() for o in r.observations}
    assert values[("UNSDG_BASELA", "MYS", 2025)] == 50.0 and values[("UNSDG_MONTRL", "MYS", 2020)] == 100.0
    assert values[("UNSDG_STKHLM", "AUT", 2020)] == 28.57143 and values[("UNSDG_MINMAT", "AUT", 2025)] == 66.67
    assert ("UNSDG_STKHLM", "MYS", 2020) not in values  # Malaysia reports no Stockholm or Minamata values
    assert all(r.skipped_areas and {c for c, _ in r.skipped_areas} == {"1", "150"} for r in normalized.values())


def test_formula_is_the_plain_mean_over_100_without_clamping():
    assert score_chmpol(100, 100, 100, 100, 100) == 1.0
    assert score_chmpol(0, 0, 0, 0, 0) == 0.0
    assert score_chmpol(50, 100, 100, 100, 50) == 0.8
    assert score_chmpol(120, 100, 100, 100, 100) == pytest.approx(1.04)  # no goalpost: an out-of-range input is not clamped


def test_registry_entry_has_no_imputation_and_no_declared_goalposts(metadata):
    definition = registry.get("CHMPOL")
    assert definition is DEFINITION and isinstance(definition, IndicatorDefinition)
    assert definition.dataset_codes == DATASETS and definition.unit == "Index"
    assert definition.imputes is False and definition.goalposts is None
    definition.check_against(metadata)  # dataset dependencies agree with the catalog


def test_incomplete_groups_stay_unscored_and_nothing_is_imputed():
    observations = full("MYS", 2020, [100, 100, 100, 100, 100]) + full("AUT", 2020, [50, 100, 100, 100, 50])[:4]  # AUT lacks ROTDAM
    result = compute_indicator(DEFINITION, observations, recipients=["AUT", "MYS", "CHE"])
    assert [(s.country_code, s.year, s.score) for s in result.scores] == [("MYS", 2020, 1.0)]
    assert result.imputed_scores == () and [(u.country_code, u.year) for u in result.unscored] == [("AUT", 2020)]


def test_fixture_scores_are_sparse(normalized):
    observations = [o for r in normalized.values() for o in r.observations]
    result = compute_indicator(DEFINITION, observations, recipients=())
    assert len(result.scores) == 8 and sorted({s.year for s in result.scores}) == [2020, 2025]
    assert "MYS" not in {s.country_code for s in result.scores} and len(result.unscored) == 13


def test_importing_chmpol_is_pure(tmp_path):
    script = textwrap.dedent(
        """
        import sys
        def hook(event, args):
            if event in ("socket.connect", "socket.getaddrinfo"):
                raise RuntimeError(f"network access attempted: {event} {args}")
        sys.addaudithook(hook)
        import sspi.indicators.chmpol
        forbidden = [m for m in sys.modules if m.split(".")[0] in ("sqlalchemy", "psycopg", "httpx", "yaml", "pandas", "pycountry") or m in ("sspi.db", "sspi.ingestion", "sspi.config")]
        assert not forbidden, forbidden
        print(sspi.indicators.chmpol.DEFINITION.code)
        """
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CHMPOL"
