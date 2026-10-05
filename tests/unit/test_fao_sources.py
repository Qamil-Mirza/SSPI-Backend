"""FAO datasets end to end without a database: canonical source metadata and
corrections, the two 1990s-average derivations, and ingestion dispatch over
one shared bulk download."""

from pathlib import Path

import pytest
import yaml

from sspi.errors import NormalizationError
from sspi.ingestion.derived import DERIVATIONS, mean_1990_1999_repeated_1990_2022, mean_1990_1999_repeated_over_source_years
from sspi.ingestion.fao import read_bulk_csv
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata
from sspi.scoring import Observation

FIXTURE = Path(__file__).parents[1] / "fixtures" / "fao" / "Inputs_LandUse_E_All_Data_(Normalized)_sample.csv"
ALL = ("UNFAO_FRSTLV", "UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_CRBNAV")


class BulkClient:
    def __init__(self):
        self.fetched = []

    def fetch_domain(self, domain):
        self.fetched.append(domain)
        return read_bulk_csv(FIXTURE.read_text(encoding="utf-8"), domain)


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


@pytest.fixture(scope="module")
def normalized(metadata):
    results, fetches = fetch_and_normalize(resolve_datasets(list(ALL), metadata), BulkClient(), metadata=metadata)
    return {dataset.code: result for dataset, result in results}, fetches


# --- metadata ---------------------------------------------------------------------------------


def test_canonical_source_metadata(metadata):
    for code in ALL:
        dataset = metadata.dataset(code)
        assert dataset.source.organization_code == "UNFAO" and dataset.source.organization_series_code is None
    assert metadata.dataset("UNFAO_FRSTLV").source.query_code == metadata.dataset("UNFAO_FRSTAV").source.query_code == "Domain=RL;Element=5110;Item=6717"
    assert metadata.dataset("UNFAO_CRBNLV").source.query_code == metadata.dataset("UNFAO_CRBNAV").source.query_code == "Domain=RL;Element=72151;Item=6646"
    assert metadata.dataset("UNFAO_FRSTLV").unit == "1000 ha" and metadata.dataset("UNFAO_CRBNLV").unit == "million t"
    assert metadata.dataset("UNFAO_FRSTAV").unit == "hectares (1990s Average)"  # legacy derived labels, kept for parity (mislabels, see PROVENANCE.yaml)
    assert metadata.dataset("UNFAO_CRBNAV").unit == "millions of kilograms (1990s Average)"


def test_element_code_correction_is_recorded_in_provenance():
    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    edits = [e for e in provenance["edits"] if e["field"] == "source.query_code" and e["file"].startswith("datasets/UNFAO_CRBN")]
    assert {e["file"] for e in edits} == {"datasets/UNFAO_CRBNLV.yaml", "datasets/UNFAO_CRBNAV.yaml"}
    assert all(e["old"] == "Domain=RL;Element=7215;Item=6646" and e["new"] == "Domain=RL;Element=72151;Item=6646" for e in edits)
    notes = [e for e in provenance["edits"] if e["field"] == "source.note" and e["file"] in ("datasets/UNFAO_CRBNAV.yaml", "datasets/UNFAO_FRSTAV.yaml")]
    assert len(notes) == 2 and all("mislabel" in e["new"] for e in notes)


# --- derivations ---------------------------------------------------------------------------------


def obs(code, country, year, value, unit="1000 ha"):
    return Observation(code, country, year, value, unit, {"source_organization": "UNFAO"})


def derived_dataset(code, unit):
    return DatasetMetadata(code=code, name=code, dataset_type="Intermediate", unit=unit, source=SourceMetadata(organization_code="UNFAO", query_code="Domain=RL;Element=5110;Item=6717"))


def test_forest_average_repeats_the_1990s_mean_for_1990_to_2022_only():
    base = [obs("UNFAO_FRSTLV", "AAA", year, float(year)) for year in range(1990, 2026)]  # 1990..2025 in the source
    rows = mean_1990_1999_repeated_1990_2022(derived_dataset("UNFAO_FRSTAV", "hectares (1990s Average)"), base)
    assert [o.year for o in rows] == list(range(1990, 2023))  # stops at 2022 whatever the source covers (DEFRST-2)
    assert {o.value for o in rows} == {sum(range(1990, 2000)) / 10} and {o.unit for o in rows} == {"hectares (1990s Average)"}
    assert rows[0].provenance["derivation"] == "mean_1990_1999_repeated_1990_2022" and rows[0].provenance["baseline_observation_count"] == 10


def test_carbon_average_repeats_the_1990s_mean_over_every_source_year():
    base = [obs("UNFAO_CRBNLV", "AAA", year, 2.0, "million t") for year in (1995, 1999, 2000, 2024, 2025)]
    base += [obs("UNFAO_CRBNLV", "BBB", year, 4.0, "million t") for year in (1998, 2010)]
    rows = mean_1990_1999_repeated_over_source_years(derived_dataset("UNFAO_CRBNAV", "millions of kilograms (1990s Average)"), base)
    years = sorted({o.year for o in base})
    assert [(o.country_code, o.year) for o in rows] == [(c, y) for c in ("AAA", "BBB") for y in years]  # every year present anywhere in the source
    assert {o.value for o in rows if o.country_code == "AAA"} == {2.0} and {o.value for o in rows if o.country_code == "BBB"} == {4.0}


def test_countries_without_a_1990s_value_get_no_average():
    base = [obs("UNFAO_FRSTLV", "NEW", year, 1.0) for year in range(2000, 2010)]
    assert mean_1990_1999_repeated_1990_2022(derived_dataset("UNFAO_FRSTAV", "x"), base) == []
    assert mean_1990_1999_repeated_over_source_years(derived_dataset("UNFAO_CRBNAV", "x"), base) == []


def test_partial_1990s_coverage_averages_what_exists():
    base = [obs("UNFAO_FRSTLV", "AAA", 1997, 1.0), obs("UNFAO_FRSTLV", "AAA", 1999, 3.0), obs("UNFAO_FRSTLV", "AAA", 2000, 9.0)]
    rows = mean_1990_1999_repeated_1990_2022(derived_dataset("UNFAO_FRSTAV", "x"), base)
    assert {o.value for o in rows} == {2.0} and rows[0].provenance["baseline_observation_count"] == 2


def test_mixed_base_datasets_are_refused():
    base = [obs("UNFAO_FRSTLV", "AAA", 1995, 1.0), obs("UNFAO_CRBNLV", "AAA", 1996, 1.0)]
    with pytest.raises(NormalizationError, match="mix datasets"):
        mean_1990_1999_repeated_1990_2022(derived_dataset("UNFAO_FRSTAV", "x"), base)


def test_derivations_are_registered():
    assert DERIVATIONS["UNFAO_FRSTAV"].base == "UNFAO_FRSTLV" and DERIVATIONS["UNFAO_FRSTAV"].transform is mean_1990_1999_repeated_1990_2022
    assert DERIVATIONS["UNFAO_CRBNAV"].base == "UNFAO_CRBNLV" and DERIVATIONS["UNFAO_CRBNAV"].transform is mean_1990_1999_repeated_over_source_years


# --- ingestion dispatch -----------------------------------------------------------------------


def test_four_datasets_share_one_domain_download(metadata):
    client = BulkClient()
    results, fetches = fetch_and_normalize(resolve_datasets(["UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_FRSTLV", "UNFAO_CRBNAV"], metadata), client, metadata=metadata)
    assert client.fetched == ["RL"] and fetches == ("RL",)
    assert [d.code for d, _ in results] == ["UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_FRSTLV", "UNFAO_CRBNAV"]


def test_derived_dataset_alone_obtains_its_base_internally(metadata):
    client = BulkClient()
    results, _ = fetch_and_normalize(resolve_datasets("UNFAO_FRSTAV", metadata), client, metadata=metadata)
    assert client.fetched == ["RL"] and [d.code for d, _ in results] == ["UNFAO_FRSTAV"]
    assert {o.dataset_code for o in results[0][1].observations} == {"UNFAO_FRSTAV"}


def test_sample_counts_and_coverage(normalized):
    results, _ = normalized
    assert {code: len(r.observations) for code, r in results.items()} == {"UNFAO_FRSTLV": 373, "UNFAO_FRSTAV": 297, "UNFAO_CRBNLV": 481, "UNFAO_CRBNAV": 432}
    forest = results["UNFAO_FRSTAV"].observations
    assert (min(o.year for o in forest), max(o.year for o in forest)) == (1990, 2022)
    carbon = results["UNFAO_CRBNAV"].observations
    assert (min(o.year for o in carbon), max(o.year for o in carbon)) == (1990, 2025)
    assert {o.country_code for o in results["UNFAO_FRSTLV"].observations} - {o.country_code for o in forest} == {"BEL", "LUX"}  # no 1990s rows: no average
    assert results["UNFAO_FRSTAV"].skipped_areas == results["UNFAO_FRSTLV"].skipped_areas


def test_mys_aut_usa_forest_rows(normalized):
    results, _ = normalized
    level = {(o.country_code, o.year): o.value for o in results["UNFAO_FRSTLV"].observations}
    assert level[("MYS", 2000)] == 18063.83 and level[("AUT", 2000)] == 2398.64 and level[("USA", 2000)] == 280976.0
    average = {(o.country_code, o.year): o.value for o in results["UNFAO_FRSTAV"].observations}
    assert average[("AUT", 2000)] == average[("AUT", 2022)] == sum(level[("AUT", y)] for y in range(1990, 2000)) / 10
