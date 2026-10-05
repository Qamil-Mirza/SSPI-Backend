"""World Bank adapter: indicator key from canonical metadata, the paged API
client, and the legacy cleaner semantics (ISO3 handling, aggregates skipped,
null/NaN/falsy values missing, year and value extraction, canonical unit).
No network, no database."""

import json
from pathlib import Path

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.worldbank import BASE_URL, WorldBankClient, indicator_key, normalize_worldbank_dataset, read_page
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

FIXTURE = Path(__file__).parents[1] / "fixtures" / "wb" / "SI.POV.GINI_sample.json"


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(series="SI.POV.GINI", query="SI.POV.GINI", unit="GINI Coeffecient", organization="WB"):
    return DatasetMetadata(code="WB_TEST", name="t", dataset_type="Indicator", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=series))


def row(iso3="MYS", country_id="MY", name="Malaysia", date="2021", value=40.7, indicator="SI.POV.GINI", **extra):
    return {"indicator": {"id": indicator, "value": "Gini index"}, "country": {"id": country_id, "value": name}, "countryiso3code": iso3, "date": date, "value": value, "unit": "", "obs_status": "", "decimal": 1, **extra}


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_names_the_indicator(catalog):
    gini = catalog.dataset("WB_GINIPT")
    assert indicator_key(gini) == "SI.POV.GINI" == gini.source.organization_series_code and gini.unit == "GINI Coeffecient"
    assert BASE_URL == "https://api.worldbank.org/v2/country/all/indicator/"


def test_indicator_key_requires_a_world_bank_dataset_with_query_and_series(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        indicator_key(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="query_code"):
        indicator_key(dataset(query=None))
    with pytest.raises(NormalizationError, match="organization_series_code"):
        indicator_key(dataset(series=None))
    with pytest.raises(NormalizationError, match="no complete dataset definition"):
        indicator_key(catalog.dataset("WB_RAILNT"))


def test_the_adapter_is_not_specific_to_the_gini_indicator():
    other = dataset(series="SP.POP.TOTL", query="SP.POP.TOTL", unit="People")
    result = normalize_worldbank_dataset(other, [row(indicator="SP.POP.TOTL", value=33938221)])
    assert [(o.dataset_code, o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("WB_TEST", "MYS", 2021, 33938221.0, "People")]


# --- normalizer ---------------------------------------------------------------------------------


def test_iso3_code_year_value_and_canonical_unit():
    result = normalize_worldbank_dataset(dataset(), [row(), row(date="2018", value=41.2), row(iso3="AUT", country_id="AT", name="Austria", value=30)])
    assert [(o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("AUT", 2021, 30.0, "GINI Coeffecient"), ("MYS", 2018, 41.2, "GINI Coeffecient"), ("MYS", 2021, 40.7, "GINI Coeffecient")]
    assert dict(result.observations[1].provenance) == {
        "source_organization": "WB",
        "source_indicator": "SI.POV.GINI",
        "description": "Gini index",
        "source_country_id": "MY",
        "source_country_name": "Malaysia",
        "source_unit": "",
        "obs_status": "",
        "decimal": 1,
    }


def test_aggregates_and_unrecognized_codes_are_skipped_and_reported():
    rows = [
        row(),
        row(iso3="WLD", country_id="1W", name="World", value=38.0),
        row(iso3="", country_id="XD", name="High income", value=None),  # no ISO3: the legacy cleaner fell back to country.id
        row(iso3="XKX", country_id="XK", name="Kosovo", value=29.0),  # not an ISO 3166-1 code
        row(iso3="", country_id="", name="nothing"),
    ]
    result = normalize_worldbank_dataset(dataset(), rows)
    assert [o.country_code for o in result.observations] == ["MYS"]
    assert result.skipped_areas == (("WLD", "World"), ("XD", "High income"), ("XKX", "Kosovo")) and result.missing_values == 0


def test_no_country_group_restriction():
    result = normalize_worldbank_dataset(dataset(), [row(iso3="NAM", country_id="NA", name="Namibia", date="1993", value=71.1)])
    assert [(o.country_code, o.year, o.value) for o in result.observations] == [("NAM", 1993, 71.1)]  # not an SSPI67 member, before 2000: kept


@pytest.mark.parametrize("value", [None, "NaN", "", 0, 0.0])
def test_null_nan_and_falsy_values_are_missing(value):
    """The legacy truthiness test (``not value``) dropped a numeric zero as well; preserved."""
    result = normalize_worldbank_dataset(dataset(), [row(value=value), row(date="2018")])
    assert [o.year for o in result.observations] == [2018] and result.missing_values == 1


def test_missing_values_of_skipped_areas_are_not_counted():
    result = normalize_worldbank_dataset(dataset(), [row(iso3="WLD", country_id="1W", name="World", value=None)])
    assert result.observations == [] and result.missing_values == 0 and result.skipped_areas == (("WLD", "World"),)


def test_string_values_are_parsed_and_malformed_ones_are_errors():
    assert normalize_worldbank_dataset(dataset(), [row(value="40.7")]).observations[0].value == 40.7
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize_worldbank_dataset(dataset(), [row(value="n/a")])
    with pytest.raises(NormalizationError, match="not a year"):
        normalize_worldbank_dataset(dataset(), [row(date="2021Q1")])
    with pytest.raises(NormalizationError, match="not finite"):
        normalize_worldbank_dataset(dataset(), [row(value="inf")])


def test_rows_of_another_indicator_and_duplicates_are_errors():
    with pytest.raises(NormalizationError, match="SP.POP.TOTL"):
        normalize_worldbank_dataset(dataset(), [row(indicator="SP.POP.TOTL")])
    with pytest.raises(DuplicateObservationError, match=r"\(MYS, 2021\)"):
        normalize_worldbank_dataset(dataset(), [row(), row(value=41.0)])


def test_rows_are_not_mutated():
    rows = json.loads(FIXTURE.read_text())[1]
    before = json.dumps(rows, sort_keys=True)
    normalize_worldbank_dataset(dataset(), rows)
    assert json.dumps(rows, sort_keys=True) == before


# --- client -------------------------------------------------------------------------------------


def test_client_follows_every_page():
    pages = {1: [row(), row(date="2018", value=41.2)], 2: [row(iso3="AUT", country_id="AT", name="Austria", value=30)]}
    requests = []

    def handler(request):
        requests.append(str(request.url))
        page = int(request.url.params["page"])
        return httpx.Response(200, json=[{"page": page, "pages": 2, "per_page": 2, "total": 3}, pages[page]])

    with WorldBankClient(http=httpx.Client(transport=httpx.MockTransport(handler)), per_page=2) as client:
        rows = client.fetch_indicator("SI.POV.GINI")
    assert [r["countryiso3code"] for r in rows] == ["MYS", "MYS", "AUT"]
    assert requests == [f"https://api.worldbank.org/v2/country/all/indicator/SI.POV.GINI?format=json&per_page=2&page={p}" for p in (1, 2)]


def test_client_reports_http_failures_api_messages_and_malformed_payloads():
    def client(response):
        return WorldBankClient(http=httpx.Client(transport=httpx.MockTransport(lambda request: response)))

    with pytest.raises(SourceRequestError, match="HTTP 502"):
        client(httpx.Response(502)).fetch_indicator("SI.POV.GINI")
    with pytest.raises(SourceResponseError, match="rejected indicator 'NOPE'"):
        client(httpx.Response(200, json=[{"message": [{"id": "120", "key": "Invalid value", "value": "The provided parameter value is not valid"}]}])).fetch_indicator("NOPE")
    with pytest.raises(SourceResponseError, match="not JSON"):
        client(httpx.Response(200, content=b"<html>")).fetch_indicator("SI.POV.GINI")
    with pytest.raises(SourceResponseError, match="page count"):
        client(httpx.Response(200, json=[{"page": 1}, []])).fetch_indicator("SI.POV.GINI")

    def refuse(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(SourceRequestError, match="failed"):
        WorldBankClient(http=httpx.Client(transport=httpx.MockTransport(refuse))).fetch_indicator("SI.POV.GINI")


def test_read_page_handles_an_indicator_with_no_rows():
    assert read_page([{"page": 0, "pages": 0, "per_page": 0, "total": 0}, None], "X") == ({"page": 0, "pages": 0, "per_page": 0, "total": 0}, [])
    with pytest.raises(SourceResponseError, match="not a"):
        read_page({"oops": 1}, "X")
    with pytest.raises(SourceResponseError, match="not objects"):
        read_page([{"pages": 1}, ["x"]], "X")
