"""REDLST: source metadata, ingestion through the generic UNSDG path, the
formula, the registry entry and the no-imputation behaviour. No database,
no network."""

import dataclasses
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from sspi.errors import IndicatorDefinitionError, NormalizationError
from sspi.indicators import IndicatorDefinition, compute_indicator, registry
from sspi.indicators.redlst import DEFINITION, score_redlst
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "unsdg" / "15_5_1_sample.json").read_text())


class FakeClient:
    def __init__(self):
        self.fetched = []

    def fetch_indicator(self, code):
        self.fetched.append(code)
        return {"15.5.1": FIXTURE["data"]}[code]


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


@pytest.fixture(scope="module")
def normalized(metadata):
    return normalize_unsdg_dataset(metadata.dataset("UNSDG_REDLST"), FIXTURE["data"])


def obs(country, year, value, **provenance):
    return Observation("UNSDG_REDLST", country, year, value, "INDEX", provenance)


# --- canonical source metadata -------------------------------------------------------


def test_canonical_source_metadata(metadata):
    dataset = metadata.dataset("UNSDG_REDLST")
    assert dataset.unit == "INDEX"
    assert dataset.source.organization_code == "UNSDG"
    assert dataset.source.query_code == "15.5.1"  # the SDG indicator requested from the UN API
    assert dataset.source.organization_series_code == "ER_RSK_LST"  # corrected from 15.5.1; see PROVENANCE.yaml edits


def test_the_series_correction_is_recorded_in_provenance():
    import yaml

    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    edit = next(e for e in provenance["edits"] if e["file"] == "datasets/UNSDG_REDLST.yaml")
    assert (edit["field"], edit["old"], edit["new"]) == ("source.organization_series_code", "15.5.1", "ER_RSK_LST")
    assert "unsdg_redlst.py" in edit["reason"]


def test_indicator_metadata(metadata):
    indicator = metadata.indicator("REDLST")
    assert (indicator.name, indicator.pillar_code, indicator.category_code) == ("IUCN Red List Index", "SUS", "ECO")
    assert indicator.dataset_codes == ("UNSDG_REDLST",)
    assert (indicator.lower_goalpost, indicator.upper_goalpost) == (0.0, 1.0)


# --- ingestion through the generic path ----------------------------------------------


def test_ingestion_uses_the_generic_path_and_the_right_query(metadata):
    client = FakeClient()
    results, fetches = fetch_and_normalize(resolve_datasets("UNSDG_REDLST", metadata), client, metadata=metadata)
    assert client.fetched == ["15.5.1"] == list(fetches)
    ((dataset, result),) = results
    assert dataset.code == "UNSDG_REDLST" and len(result.observations) == 230


def test_normalized_observations(normalized):
    observations = normalized.observations
    assert len(observations) == 230 and {o.dataset_code for o in observations} == {"UNSDG_REDLST"}
    assert sorted({o.country_code for o in observations}) == ["ALB", "AUT", "KEN", "MYS", "USA"]
    assert {o.unit for o in observations} == {"INDEX"}
    for country in ("ALB", "AUT", "KEN", "MYS", "USA"):
        assert [o.year for o in observations if o.country_code == country] == list(range(1980, 2026))  # no year filter
    values = {(o.country_code, o.year): o.value for o in observations}
    assert values[("MYS", 2018)] == 0.83317 and values[("MYS", 2023)] == 0.81645
    assert values[("AUT", 2018)] == 0.95597 and values[("AUT", 2020)] == 0.95275 and values[("USA", 2018)] == 0.82657
    assert normalized.skipped_areas == (("1", "World"), ("150", "Europe"))  # regional aggregates have no ISO3 code


def test_provenance_keeps_source_identifiers_and_flags(normalized):
    mys = next(o for o in normalized.observations if (o.country_code, o.year) == ("MYS", 2020))
    assert mys.provenance == {
        "source_organization": "UNSDG",
        "source_indicator": "15.5.1",
        "source_series": "ER_RSK_LST",
        "source_geo_area_code": "458",
        "source_geo_area_name": "Malaysia",
        "nature": "E",
        "observation_status": "",
    }
    assert {o.provenance["nature"] for o in normalized.observations} == {"E"}  # kept, never used to filter


def test_missing_source_values_are_counted_and_not_stored(normalized):
    empty = sum(1 for row in FIXTURE["data"] if row["geoAreaCode"] not in ("1", "150") for e in json.loads(row["years"]) if e["value"] == "")
    assert empty > 0 and normalized.missing_values == empty
    assert (("MYS", 1979) not in {(o.country_code, o.year) for o in normalized.observations})


def test_a_removed_value_stays_missing(metadata):
    rows = [dict(r) for r in FIXTURE["data"] if r["geoAreaCode"] == "458"]
    years = json.loads(rows[0]["years"])
    rows[0]["years"] = json.dumps([{"year": e["year"], "value": ""} if e["year"] == "[2020]" else e for e in years])
    result = normalize_unsdg_dataset(metadata.dataset("UNSDG_REDLST"), rows)
    assert 2020 not in {o.year for o in result.observations} and len(result.observations) == 45


def test_unit_disagreement_is_refused(metadata):
    rows = [dict(r) for r in FIXTURE["data"]]
    rows[0]["units"] = "PERCENT"
    with pytest.raises(NormalizationError, match="unit"):
        normalize_unsdg_dataset(metadata.dataset("UNSDG_REDLST"), rows)


def test_the_uncorrected_legacy_series_code_could_not_select_any_row(metadata):
    dataset = metadata.dataset("UNSDG_REDLST")
    legacy = dataclasses.replace(dataset, source=dataclasses.replace(dataset.source, organization_series_code="15.5.1"))
    with pytest.raises(NormalizationError, match="ER_RSK_LST"):
        normalize_unsdg_dataset(legacy, FIXTURE["data"])


# --- formula and definition ----------------------------------------------------------


@pytest.mark.parametrize("value, expected", [(-0.2, 0.0), (0.0, 0.0), (0.25, 0.25), (0.83317, 0.83317), (1.0, 1.0), (1.3, 1.0)])
def test_goalpost_behaviour(value, expected):
    assert score_redlst(value) == expected


def test_registry_resolves_redlst_with_no_imputation_configuration():
    definition = registry.get("REDLST")
    assert definition is DEFINITION and isinstance(definition, IndicatorDefinition)
    assert definition.dataset_codes == ("UNSDG_REDLST",) and definition.unit == "Index"
    assert definition.imputation is None and definition.recipient_group is None and definition.auxiliary_datasets == ()
    assert definition.imputes is False and definition.goalposts == (0, 1)
    assert registry.get("BIODIV").imputes is True and registry.get("BIODIV").goalposts is None  # unchanged


def test_definition_agrees_with_metadata_on_datasets_and_goalposts(metadata):
    DEFINITION.check_against(metadata)  # must not raise


def test_goalpost_disagreement_with_metadata_fails_clearly(metadata):
    drifted = dataclasses.replace(DEFINITION, goalposts=(0.5, 1))
    with pytest.raises(IndicatorDefinitionError, match="goalposts") as info:
        drifted.check_against(metadata)
    assert "REDLST" in str(info.value) and "(0.0, 1.0)" in str(info.value) and "(0.5, 1)" in str(info.value)


def test_run_checks_goalposts_before_touching_the_database(metadata):
    from sspi.indicators import run_indicator

    class Drifted:
        @staticmethod
        def get(code):
            return dataclasses.replace(DEFINITION, goalposts=(0.5, 1))

    with pytest.raises(IndicatorDefinitionError, match="goalposts"):
        run_indicator("REDLST", database=None, metadata=metadata, registry=Drifted)


# --- no imputation -------------------------------------------------------------------


def test_missing_observations_produce_no_score_and_nothing_is_imputed():
    observations = [obs("MYS", 2005, 0.9), obs("MYS", 2010, 0.8), obs("USA", 2030, 1.3)]  # gap 2006-2009, nothing before/after
    result = compute_indicator(DEFINITION, observations, recipients=["AUT", "CHE", "MYS"])
    assert result.imputed_scores == () and result.unscored == ()
    assert [(s.country_code, s.year, s.score) for s in result.scores] == [("MYS", 2005, 0.9), ("MYS", 2010, 0.8), ("USA", 2030, 1.0)]
    assert all(not o.provenance.get("imputed", False) for s in result.scores for o in s.inputs)


def test_recipients_do_not_affect_the_result(normalized):
    a = compute_indicator(DEFINITION, normalized.observations, recipients=[])
    b = compute_indicator(DEFINITION, reversed(normalized.observations), recipients=["AUT", "CHE", "KEN"])
    assert a == b and len(a.scores) == 230


def test_run_does_not_load_the_country_catalog(monkeypatch):
    from sspi.indicators import run_indicator
    from sspi.metadata import CountryCatalog

    monkeypatch.setattr(CountryCatalog, "load", classmethod(lambda cls: pytest.fail("CountryCatalog loaded for an indicator with no imputation")))

    class NoRows:
        def transaction(self):
            raise RuntimeError("reached the database")

    with pytest.raises(RuntimeError, match="reached the database"):
        run_indicator("REDLST", NoRows())


def test_importing_redlst_is_pure(tmp_path):
    script = textwrap.dedent(
        """
        import sys
        opened = []
        def hook(event, args):
            if event == "open":
                opened.append(str(args[0]))
            if event in ("socket.connect", "socket.getaddrinfo"):
                raise RuntimeError(f"network access attempted: {event} {args}")
        sys.addaudithook(hook)
        import sspi.indicators.registry
        import sspi.indicators.redlst
        forbidden = [m for m in sys.modules if m.split(".")[0] in ("sqlalchemy", "psycopg", "httpx", "yaml", "pandas", "pycountry")
                     or m in ("sspi.db", "sspi.ingestion", "sspi.config")]
        assert not forbidden, forbidden
        data_opens = [p for p in opened if "/sspi/" in p.replace("\\\\", "/") and not p.endswith((".py", ".pyc"))]
        assert not data_opens, data_opens
        print(sspi.indicators.registry.get("REDLST").code, sspi.indicators.registry.codes())
        """
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "REDLST ('BIODIV', 'REDLST', 'CHMPOL', 'WATMAN', 'NITROG', 'DEFRST', 'CARBON', 'ISHRAT', 'GINIPT', 'EMPLOY', 'COLBAR', 'ALTNRG', 'NRGINT', 'AIRPOL', 'BEEFMK', 'COALPW', 'GTRANS', 'MSWGEN', 'PUPTCH', 'ENRPRI', 'ENRSEC', 'YRSEDU')"
