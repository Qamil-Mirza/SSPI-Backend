"""EPI adapter: edition archive table, archive reading, the legacy parser
semantics (iso column, melt, NA and negative drop, Index unit) and the
NITROG definition. No network, no database."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml

from sspi.errors import DuplicateObservationError, IndicatorDefinitionError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.indicators import compute_indicator, registry
from sspi.indicators.nitrog import DEFINITION, score_nitrog
from sspi.ingestion.epi import ARCHIVES, EPIClient, archive_key, normalize_epi_csv, normalize_epi_dataset, read_archive, series_of
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

FIXTURE = Path(__file__).parents[1] / "fixtures" / "epi" / "epi2024indicators_P5_Indicator_SNM_ind_na.csv"
SMALL = "code,iso,country,SNM.ind.2020,SNM.ind.2021,SNM.ind.2022\n4,AFG,Afghanistan,24.3,NA,-7777\n458,MYS,Malaysia,50.5,51,52.25\n"


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(series="SNM", query="epi2026_indicators_na_2026-08-31", unit="Index", organization="EPI"):
    return DatasetMetadata(code="EPI_TEST", name="t", dataset_type="Indicator", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=series))


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


# --- metadata and editions --------------------------------------------------------------------


def test_canonical_source_metadata_and_the_edition_change(catalog):
    nitrog = catalog.dataset("EPI_NITROG")
    assert nitrog.source.organization_code == "EPI" and nitrog.source.organization_series_code == "SNM" and nitrog.unit == "Index"
    assert archive_key(nitrog) == nitrog.source.query_code == "epi2026_indicators_na_2026-08-31"
    assert set(ARCHIVES) >= {"epi2024indicators", "epi2026_indicators_na_2026-08-31"}  # legacy and current editions both resolvable
    assert ARCHIVES["epi2024indicators"] == "https://epi.yale.edu/downloads/epi2024indicators.zip"
    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    edit = next(e for e in provenance["edits"] if e["file"] == "datasets/EPI_NITROG.yaml" and e["field"] == "source.query_code")
    assert edit["old"] == "epi2024indicators" and edit["new"] == "epi2026_indicators_na_2026-08-31" and "NITROG-1" in edit["reason"]


def test_archive_key_requires_an_epi_dataset_with_edition_and_series(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        archive_key(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="query_code"):
        archive_key(dataset(query=None))
    with pytest.raises(NormalizationError, match="series"):
        archive_key(dataset(series=None))


def test_series_code_is_the_file_name_up_to_the_first_underscore():
    assert series_of("P5_Indicator/SNM_ind_na.csv") == "SNM" and series_of("SNM_ind_na.csv") == "SNM" and series_of("PSU_ind_mvc.csv") == "PSU"


# --- archives ------------------------------------------------------------------------------------


def test_archive_reading_drops_directories_and_macos_metadata_and_keeps_basenames():
    files = read_archive(zipped({"P5_Indicator/": "", "__MACOSX/P5_Indicator/._SNM_ind_na.csv": "x", "P5_Indicator/SNM_ind_na.csv": SMALL, "P5_Indicator/README.txt": "no"}), "e")
    assert files == {"SNM_ind_na.csv": SMALL}


def test_archive_reading_rejects_html_pages_and_empty_archives():
    with pytest.raises(SourceResponseError, match="not a zip"):
        read_archive(b"<!DOCTYPE html><html></html>", "epi2024indicators")
    with pytest.raises(SourceResponseError, match="no CSV"):
        read_archive(zipped({"README.txt": "x"}), "e")


def test_client_fetches_the_registered_archive_url():
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=zipped({"SNM_ind_na.csv": SMALL}))

    with EPIClient(http=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        assert client.fetch_archive("epi2026_indicators_na_2026-08-31") == {"SNM_ind_na.csv": SMALL}
        with pytest.raises(SourceRequestError, match="no EPI archive URL"):
            client.fetch_archive("epi2030")
    assert requested == [ARCHIVES["epi2026_indicators_na_2026-08-31"]]


def test_client_reports_http_failures():
    with EPIClient(http=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))) as client:
        with pytest.raises(SourceRequestError, match="HTTP 404"):
            client.fetch_archive("epi2024indicators")


# --- parser --------------------------------------------------------------------------------------


def test_parser_melts_wide_rows_and_drops_na_and_negative_values():
    result = normalize_epi_csv(dataset(), SMALL, edition="e", file_name="SNM_ind_na.csv")
    records = [(o.country_code, o.year, o.value, o.unit) for o in result.observations]
    assert records == [("AFG", 2020, 24.3, "Index"), ("MYS", 2020, 50.5, "Index"), ("MYS", 2021, 51.0, "Index"), ("MYS", 2022, 52.25, "Index")]
    assert result.missing_values == 2 and result.skipped_areas == ()
    afg = result.observations[0].provenance
    assert afg["source_column"] == "SNM.ind.2020" and afg["source_code"] == "4" and afg["source_country_name"] == "Afghanistan" and afg["source_edition"] == "e"


def test_iso_column_is_used_as_published_without_remapping():
    text = "code,iso,country,SNM.ind.2020\n999,XKX,Kosovo,10\n"
    result = normalize_epi_csv(dataset(), text)
    assert [(o.country_code, o.value) for o in result.observations] == [("XKX", 10.0)]


def test_dataset_selects_exactly_one_file_by_series():
    archive = {"SNM_ind_na.csv": SMALL, "PSU_ind_na.csv": SMALL.replace("SNM", "PSU")}
    assert len(normalize_epi_dataset(dataset(), archive).observations) == 4
    assert len(normalize_epi_dataset(dataset(series="PSU"), archive).observations) == 4
    with pytest.raises(NormalizationError, match="expected one file for series 'XXX'"):
        normalize_epi_dataset(dataset(series="XXX"), archive)
    with pytest.raises(NormalizationError, match="expected one file"):
        normalize_epi_dataset(dataset(), {"SNM_ind_na.csv": SMALL, "SNM_ind_mvc.csv": SMALL})


@pytest.mark.parametrize("text, message", [
    ("code,country,SNM.ind.2020\n4,Afghanistan,1\n", "lacks columns \\['iso'\\]"),
    ("code,iso,country,SNM.ind\n4,AFG,Afghanistan,1\n", "no four-digit year"),
    ("code,iso,country\n4,AFG,Afghanistan\n", "no year columns"),
    ("code,iso,country,SNM.ind.2020\n4,AFG,Afghanistan,abc\n", "not numeric"),
    ("code,iso,country,SNM.ind.2020\n4,,Afghanistan,1\n", "empty iso"),
])
def test_malformed_files_are_errors(text, message):
    with pytest.raises(NormalizationError, match=message):
        normalize_epi_csv(dataset(), text)


def test_duplicate_iso_rows_collide():
    with pytest.raises(DuplicateObservationError, match="AFG"):
        normalize_epi_csv(dataset(), "code,iso,country,SNM.ind.2020\n4,AFG,A,1\n5,AFG,B,2\n")


def test_unit_must_be_index():
    with pytest.raises(NormalizationError, match="Index"):
        normalize_epi_csv(dataset(unit="Percent"), SMALL)


def test_fixture_counts(catalog):
    result = normalize_epi_csv(catalog.dataset("EPI_NITROG"), FIXTURE.read_text(encoding="utf-8"))
    assert len(result.observations) == 5820 and result.missing_values == 780
    mys = {o.year: o.value for o in result.observations if o.country_code == "MYS"}
    assert (min(mys), max(mys)) == (1995, 2024)


# --- ingestion dispatch -----------------------------------------------------------------------


class ArchiveClient:
    def __init__(self):
        self.fetched = []

    def fetch_archive(self, archive):
        self.fetched.append(archive)
        return {"SNM_ind_na.csv": FIXTURE.read_text(encoding="utf-8")}


def test_epi_nitrog_is_ingestible_through_the_generic_runner(catalog):
    client = ArchiveClient()
    results, fetches = fetch_and_normalize(resolve_datasets("EPI_NITROG", catalog), client, metadata=catalog)
    assert client.fetched == ["epi2026_indicators_na_2026-08-31"] == list(fetches)
    assert [(d.code, len(r.observations)) for d, r in results] == [("EPI_NITROG", 5820)]


def test_mixed_organization_requests_take_a_client_per_organization(catalog):
    class Forbidden:
        def fetch_indicator(self, code):
            raise AssertionError("UNSDG client must not be used for an EPI dataset")

    results, fetches = fetch_and_normalize(resolve_datasets(["EPI_NITROG"], catalog), {"EPI": ArchiveClient(), "UNSDG": Forbidden()}, metadata=catalog)
    assert fetches == ("epi2026_indicators_na_2026-08-31",) and results[0][0].code == "EPI_NITROG"


# --- NITROG definition ------------------------------------------------------------------------------


def test_definition_is_registered_with_no_imputation(catalog):
    assert registry.get("NITROG") is DEFINITION
    assert DEFINITION.dataset_codes == ("EPI_NITROG",) and DEFINITION.imputation is None and DEFINITION.goalposts == (0, 100)
    DEFINITION.check_against(catalog)


@pytest.mark.parametrize("value, score", [(-1.0, 0.0), (0.0, 0.0), (24.3, 0.243), (100.0, 1.0), (120.0, 1.0)])
def test_score_is_the_source_index_clamped_to_unit_interval(value, score):
    assert score_nitrog(value) == score


def test_goalposts_are_checked_against_metadata(catalog):
    from dataclasses import replace

    with pytest.raises(IndicatorDefinitionError, match="goalposts"):
        replace(DEFINITION, goalposts=(0, 1)).check_against(catalog)


def test_nothing_is_imputed(catalog):
    result = normalize_epi_csv(catalog.dataset("EPI_NITROG"), SMALL)
    run = compute_indicator(DEFINITION, result.observations)
    assert len(run.observed_scores) == 4 and run.imputed_scores == () and run.unscored == ()
