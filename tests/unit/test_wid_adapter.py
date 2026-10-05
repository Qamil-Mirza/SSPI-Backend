"""WID adapter: series selection from canonical metadata, the bulk archive
client, the legacy cleaner semantics (SSPI67 files, variable and percentile,
2000-2024, unit from the metadata file) and the legacy float32 value
representation. No network, no database."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.wid import ARCHIVES, LEGACY_COUNTRY_GROUP, LEGACY_YEARS, SeriesSelection, WIDArchive, WIDClient, archive_key, country_file_names, legacy_float32_value, metadata_unit, normalize_wid_dataset, series_selection
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

HEADER = "country;variable;percentile;year;value;age;pop;data_quality\n"
METADATA = "country;variable;age;pop;countryname;shortname;unit\nMY;sptincj992;992;j;Malaysia;Pre-tax national income;share\nMY;aptincj992;992;j;Malaysia;Pre-tax national income;MYR\n"
DATA = HEADER + (
    "MY;aptincj992;p0p50;2000;11885.3;992;j;2\n"
    "MY;sptincj992;p0p50;1999;0.1375;992;j;2\n"
    "MY;sptincj992;p0p50;2000;0.1388;992;j;2\n"
    "MY;sptincj992;p0p50;2024;0.1921;992;j;2\n"
    "MY;sptincj992;p0p50;2025;0.2;992;j;2\n"
    "MY;sptincj992;p90p100;2000;0.4;992;j;2\n"
    "MY;sptincj992;p99p100;2000;0.15;992;j;2\n"
)


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(variable="sptincj992", percentile="p0p50", unit="share; percentile p0p50; sptincj992", query="wid_all_data", organization="WID", dimensions="default"):
    dims = {"percentile": percentile} if dimensions == "default" else dimensions
    return DatasetMetadata(code="WID_TEST", name="t", dataset_type="Intermediate", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=variable, dimensions=dims))


def archive(data=DATA, metadata=METADATA):
    return {"WID_data_MY.csv": data, "WID_metadata_MY.csv": metadata}


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_selects_the_exact_wid_series(catalog):
    assert series_selection(catalog.dataset("WID_NINCSH_PRETAX_P0P50")) == SeriesSelection("wid_all_data", "sptincj992", "p0p50")
    assert series_selection(catalog.dataset("WID_NINCSH_PRETAX_P90P100")) == SeriesSelection("wid_all_data", "sptincj992", "p90p100")
    assert archive_key(catalog.dataset("WID_NINCSH_PRETAX_P0P50")) == "wid_all_data" and ARCHIVES["wid_all_data"] == "https://wid.world/bulk_download/wid_all_data.zip"
    assert (LEGACY_COUNTRY_GROUP, LEGACY_YEARS) == ("SSPI67", (2000, 2024))


def test_series_code_dimension_and_float32_note_are_recorded_in_provenance(catalog):
    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    for code, percentile in (("WID_NINCSH_PRETAX_P0P50", "p0p50"), ("WID_NINCSH_PRETAX_P90P100", "p90p100")):
        edits = {e["field"]: e for e in provenance["edits"] if e["file"] == f"datasets/{code}.yaml"}
        assert edits["source.organization_series_code"]["old"] is None and edits["source.organization_series_code"]["new"] == "sptincj992"
        assert edits["source.dimensions"]["new"] == {"percentile": percentile}
        assert "float32" in edits["source.note"]["new"] and "not a methodology change" in edits["source.note"]["reason"]
        assert "0.1921000034" in catalog.dataset(code).source.note


def test_selection_requires_a_wid_dataset_with_variable_and_one_percentile(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        series_selection(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="query_code"):
        series_selection(dataset(query=None))
    with pytest.raises(NormalizationError, match="organization_series_code"):
        series_selection(dataset(variable=None))
    for bad in (None, {"percentile": "p0p50", "age": "992"}, {"pop": "j"}):
        with pytest.raises(NormalizationError, match="percentile"):
            series_selection(dataset(dimensions=bad))
    with pytest.raises(NormalizationError, match="no complete dataset definition"):
        series_selection(catalog.dataset("WB_RAILNT"))


# --- float32 representation ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("published", "stored"),
    [("0.1921", 0.1921000034), ("0.3653", 0.3652999997), ("0.1665", 0.1665000021), ("0.4628", 0.4627999961), ("0.5", 0.5), ("0", 0.0), ("1", 1.0), ("11885.3", 11885.2998046875), ("-0.25", -0.25), ("-0.1921", -0.1921000034)],
)
def test_legacy_float32_value_reproduces_the_stored_number(published, stored):
    assert legacy_float32_value(published) == stored


def test_legacy_float32_value_rejects_what_the_representation_cannot_hold():
    for bad in ("abc", "", "nan", "inf", "1e40", "1e16"):
        with pytest.raises(NormalizationError):
            legacy_float32_value(bad)


# --- normalizer ---------------------------------------------------------------------------------


def test_keeps_the_variable_percentile_and_legacy_years_only():
    result = normalize_wid_dataset(dataset(), archive(), countries=["MYS"])
    assert [(o.dataset_code, o.country_code, o.year, o.value) for o in result.observations] == [("WID_TEST", "MYS", 2000, 0.1387999952), ("WID_TEST", "MYS", 2024, 0.1921000034)]
    assert {o.unit for o in result.observations} == {"share; percentile p0p50; sptincj992"}
    assert result.skipped_areas == () and result.missing_values == 0
    top = normalize_wid_dataset(dataset(percentile="p90p100", unit="share; percentile p90p100; sptincj992"), archive(), countries=["MYS"])
    assert [(o.year, o.value) for o in top.observations] == [(2000, 0.400000006)]


def test_provenance_keeps_the_published_text_and_the_source_dimensions():
    (first, _) = normalize_wid_dataset(dataset(), archive(), countries=["MYS"]).observations
    assert dict(first.provenance) == {
        "source_organization": "WID",
        "source_archive": "wid_all_data",
        "source_file": "WID_data_MY.csv",
        "source_variable": "sptincj992",
        "source_percentile": "p0p50",
        "source_age": "992",
        "source_population": "j",
        "source_value": "0.1388",
        "value_representation": "float32, ten decimals (legacy cleaner)",
    }


def test_countries_default_to_the_sspi67_members_and_each_needs_both_files():
    with pytest.raises(NormalizationError, match=r"no \['WID_data_AR.csv', 'WID_metadata_AR.csv'\] for ARG"):
        normalize_wid_dataset(dataset(), archive())  # SSPI67 starts with ARG; the legacy cleaner asserted the same
    with pytest.raises(NormalizationError, match=r"WID_metadata_MY.csv"):
        normalize_wid_dataset(dataset(), {"WID_data_MY.csv": DATA}, countries=["MYS"])
    with pytest.raises(NormalizationError, match="alpha-3"):
        normalize_wid_dataset(dataset(), archive(), countries=["XKX"])
    assert country_file_names("MY") == ("WID_data_MY.csv", "WID_metadata_MY.csv")


def test_unit_comes_from_the_metadata_file_and_must_match_the_canonical_unit():
    assert metadata_unit(METADATA, "sptincj992") == "share" and metadata_unit(METADATA, "aptincj992") == "MYR"
    assert metadata_unit(METADATA, "nothere") == "No unit available"
    with pytest.raises(NormalizationError, match="canonical unit"):
        normalize_wid_dataset(dataset(unit="percent; percentile p0p50; sptincj992"), archive(), countries=["MYS"])
    with pytest.raises(NormalizationError, match="No unit available"):
        normalize_wid_dataset(dataset(), archive(metadata="country;variable;unit\n"), countries=["MYS"])
    trailing_newline = dataset(unit="share; percentile p0p50; sptincj992\n")  # the canonical YAML block scalar ends with a newline
    assert {o.unit for o in normalize_wid_dataset(trailing_newline, archive(), countries=["MYS"]).observations} == {"share; percentile p0p50; sptincj992"}


def test_duplicates_empty_values_and_malformed_rows_are_errors():
    with pytest.raises(DuplicateObservationError, match=r"\(MYS, 2000\)"):
        normalize_wid_dataset(dataset(), archive(DATA + "MY;sptincj992;p0p50;2000;0.14;992;j;2\n"), countries=["MYS"])
    with pytest.raises(NormalizationError, match="empty value"):
        normalize_wid_dataset(dataset(), archive(HEADER + "MY;sptincj992;p0p50;2001;;992;j;2\n"), countries=["MYS"])
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize_wid_dataset(dataset(), archive(HEADER + "MY;sptincj992;p0p50;2001;x;992;j;2\n"), countries=["MYS"])
    with pytest.raises(NormalizationError, match="year is not an integer"):
        normalize_wid_dataset(dataset(), archive(HEADER + "MY;sptincj992;p0p50;20x1;0.1;992;j;2\n"), countries=["MYS"])
    with pytest.raises(NormalizationError, match="header lacks columns"):
        normalize_wid_dataset(dataset(), archive("country;variable;year;value\n"), countries=["MYS"])


def test_no_matching_rows_is_an_empty_series_not_an_error():
    assert normalize_wid_dataset(dataset(), archive(HEADER), countries=["MYS"]).observations == []


# --- client -------------------------------------------------------------------------------------


def test_client_streams_the_archive_once_and_reads_members_on_demand():
    requests = []
    payload = zipped({"WID_data_MY.csv": DATA, "WID_metadata_MY.csv": METADATA, "README.md": "x", "__MACOSX/._WID_data_MY.csv": "junk"})

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=payload)

    with WIDClient(http=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        opened = client.fetch_archive("wid_all_data")
        assert isinstance(opened, WIDArchive) and sorted(opened) == ["README.md", "WID_data_MY.csv", "WID_metadata_MY.csv"] and len(opened) == 3
        assert opened["WID_data_MY.csv"] == DATA and "WID_data_SG.csv" not in opened
        result = normalize_wid_dataset(dataset(), opened, countries=["MYS"])
    assert requests == ["https://wid.world/bulk_download/wid_all_data.zip"] and len(result.observations) == 2
    with pytest.raises(ValueError):
        opened["WID_data_MY.csv"]  # closed with the client: the temporary file is gone


def test_client_reports_unknown_archives_http_failures_and_non_zip_payloads():
    def handler(request):
        return httpx.Response(503)

    client = WIDClient(http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(SourceRequestError, match="no WID archive URL"):
        client.fetch_archive("wid_other")
    with pytest.raises(SourceRequestError, match="HTTP 503"):
        client.fetch_archive("wid_all_data")
    html = WIDClient(http=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"<html></html>"))))
    with pytest.raises(SourceResponseError, match="not a zip file"):
        html.fetch_archive("wid_all_data")

    def refuse(request):
        raise httpx.ConnectError("refused")

    down = WIDClient(http=httpx.Client(transport=httpx.MockTransport(refuse)))
    with pytest.raises(SourceRequestError, match="failed"):
        down.fetch_archive("wid_all_data")
