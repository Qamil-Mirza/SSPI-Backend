"""The WHO GHO OData client and normalizer on synthetic messages written here
(not WHO data): paging, request failures, the legacy cleaner's selection
semantics, and the cases the legacy parity fixtures do not reach (a missing
number, a non-storable country code, disaggregated rows, duplicates, rows of
another indicator). No network."""

import dataclasses
import math

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion import SOURCES, WHOClient, normalize_who_dataset
from sspi.ingestion.who import BASE_URL, GHOIndicatorData, indicator_key, read_page
from sspi.metadata import MetadataCatalog

CATALOG = MetadataCatalog.load()
DATASET = CATALOG.dataset("WHO_PHYSPC")  # HWF_0001, unit "Doctors per 10000", no dimension filter


def row(country="AUT", year=2020, value=50.5, *, kind="COUNTRY", code="HWF_0001", display=None, **fields):
    record = {
        "Id": 1, "IndicatorCode": code, "SpatialDimType": kind, "SpatialDim": country, "TimeDimType": "YEAR", "TimeDim": year,
        "Dim1Type": None, "Dim1": None, "Dim2Type": None, "Dim2": None, "Dim3Type": None, "Dim3": None,
        "DataSourceDimType": None, "DataSourceDim": None, "Value": display if display is not None else ("No data" if value is None else str(value)),
        "NumericValue": value, "Low": None, "High": None, "Comments": None, "Date": "2001-02-03T04:05:06.7+01:00",
    }
    record.update(fields)
    return record


def data(*rows, code="HWF_0001"):
    return GHOIndicatorData(code, BASE_URL + code, f"https://ghoapi.azureedge.net/api/$metadata#{code}", 1, tuple(rows))


def with_dimensions(dataset, dimensions):
    return dataclasses.replace(dataset, source=dataclasses.replace(dataset.source, dimensions=dimensions))


# --- client ------------------------------------------------------------------------------------


def test_one_request_per_indicator_at_the_configured_base_url():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"@odata.context": "ctx", "value": [row()]})

    with WHOClient(http=httpx.Client(transport=httpx.MockTransport(handler)), base_url="https://example.org/gho/api") as client:
        result = client.fetch_indicator("HWF_0001")
    assert seen == ["https://example.org/gho/api/HWF_0001"]  # no query string: every row of the indicator, as legacy
    assert (result.indicator, result.url, result.odata_context, result.pages, len(result.rows)) == ("HWF_0001", "https://example.org/gho/api/HWF_0001", "ctx", 1, 1)
    assert WHOClient(http=httpx.Client()).base_url == BASE_URL == "https://ghoapi.azureedge.net/api/"


def test_odata_next_links_are_followed_in_order():
    pages = {
        BASE_URL + "HWF_0001": {"value": [row(year=2000)], "@odata.nextLink": BASE_URL + "HWF_0001?$skip=1"},
        BASE_URL + "HWF_0001?$skip=1": {"value": [row(year=2001)], "@odata.nextLink": BASE_URL + "HWF_0001?$skip=2"},
        BASE_URL + "HWF_0001?$skip=2": {"value": [row(year=2002)]},
    }
    client = WHOClient(http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=pages[str(r.url).replace("%24", "$")]))))
    result = client.fetch_indicator("HWF_0001")
    assert result.pages == 3 and [r["TimeDim"] for r in result.rows] == [2000, 2001, 2002]


@pytest.mark.parametrize(
    ("response", "error", "match"),
    [
        (httpx.Response(404), SourceRequestError, "HTTP 404"),  # the service's answer to an unknown code
        (httpx.Response(200, content=b"<html>"), SourceResponseError, "not JSON"),
        (httpx.Response(200, json={"error": "x"}), SourceResponseError, "no 'value' list"),
        (httpx.Response(200, json={"value": [1]}), SourceResponseError, "not objects"),
        (httpx.Response(200, json={"value": [], "@odata.nextLink": 3}), SourceResponseError, "nextLink"),
    ],
)
def test_request_and_response_failures_are_reported(response, error, match):
    client = WHOClient(http=httpx.Client(transport=httpx.MockTransport(lambda r: response)))
    with pytest.raises(error, match=match):
        client.fetch_indicator("NOT_A_CODE")


def test_the_source_is_registered_by_organization_and_keyed_by_query_code():
    assert SOURCES["WHO"].organization_code == "WHO" and SOURCES["WHO"].fetch_key(DATASET) == "HWF_0001" == indicator_key(DATASET)
    assert read_page({"value": []}, "X") == ([], None, None)


# --- normalizer: the legacy cleaner's selection ------------------------------------------------


def test_only_country_rows_are_kept_and_aggregates_are_reported():
    result = normalize_who_dataset(DATASET, data(row(), row("GLOBAL", kind="GLOBAL"), row("EUR", kind="REGION"), row("WB_HI", kind="WORLDBANKINCOMEGROUP"), row("SDG1", kind="UNREGION")))
    assert [(o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("AUT", 2020, 50.5, "Doctors per 10000")]
    assert result.skipped_areas == (("GLOBAL", "GLOBAL"), ("EUR", "REGION"), ("WB_HI", "WORLDBANKINCOMEGROUP"), ("SDG1", "UNREGION"))


def test_no_data_rows_are_missing_values_and_a_reported_zero_is_kept():
    result = normalize_who_dataset(DATASET, data(row(year=2019, value=None), row(year=2020, value=0.0), row(year=2021, value=0)))
    assert result.missing_values == 1 and [(o.year, o.value) for o in result.observations] == [(2020, 0.0), (2021, 0.0)]
    assert all(isinstance(o.value, float) for o in result.observations)


def test_the_number_is_numeric_value_never_the_rounded_display_value():
    (observation,) = normalize_who_dataset(DATASET, data(row(value=95.7, display="96"))).observations
    assert observation.value == 95.7 and observation.provenance["display_value"] == "96"


@pytest.mark.parametrize("bad", [None, "12", True])
def test_a_missing_number_that_is_not_no_data_is_an_error(bad):
    with pytest.raises(NormalizationError, match="not a number"):  # legacy float(None) raised
        normalize_who_dataset(DATASET, data(row(value=bad, display="12")))


def test_a_non_finite_number_is_an_error():
    with pytest.raises(NormalizationError, match="not finite"):
        normalize_who_dataset(DATASET, data(row(value=math.inf, display="inf")))


def test_country_codes_are_kept_as_served_but_must_be_storable():
    (observation,) = normalize_who_dataset(DATASET, data(row("XKX"))).observations  # not ISO 3166, as legacy kept it
    assert observation.country_code == "XKX"
    with pytest.raises(NormalizationError, match="cannot be stored"):
        normalize_who_dataset(DATASET, data(row("SDN736")))


def test_rows_of_another_indicator_and_unparsable_years_are_errors():
    with pytest.raises(NormalizationError, match="belongs to indicator 'WHS4_100'"):
        normalize_who_dataset(DATASET, data(row(code="WHS4_100")))
    with pytest.raises(NormalizationError, match="not a year"):
        normalize_who_dataset(DATASET, data(row(year="2010-2015", TimeDimType="YEARRANGE")))


def test_duplicate_identities_are_refused_with_the_distinguishing_field():
    with pytest.raises(DuplicateObservationError, match=r"\('AUT', 2020\).*Dim1"):
        normalize_who_dataset(DATASET, data(row(Dim1="SEX_FMLE", Dim1Type="SEX"), row(Dim1="SEX_MLE", Dim1Type="SEX", value=40.0)))


def test_declared_dimensions_select_one_slice_and_are_recorded():
    dataset = with_dimensions(DATASET, {"Dim1": "SEX_BTSX"})
    rows = [row(Dim1="SEX_FMLE", Dim1Type="SEX"), row(Dim1="SEX_BTSX", Dim1Type="SEX", value=45.0), row(Dim1="SEX_MLE", Dim1Type="SEX", year=2021, value=None), row(Dim1="SEX_BTSX", Dim1Type="SEX", year=2021, value=None)]
    result = normalize_who_dataset(dataset, data(*rows))
    (observation,) = result.observations
    assert observation.value == 45.0 and observation.provenance["source_dimensions"] == {"Dim1": "SEX_BTSX"} and observation.provenance["dim1"] == "SEX_BTSX"
    assert result.missing_values == 1  # only the selected slice's "No data" row is counted
    with pytest.raises(NormalizationError, match="not GHO row fields"):
        normalize_who_dataset(with_dimensions(DATASET, {"sex": "BOTHSEX"}), data(row()))


def test_metadata_must_name_the_indicator_and_unit():
    with pytest.raises(NormalizationError, match="not 'WHO'"):
        indicator_key(CATALOG.dataset("UNSDG_CSTUNT"))
    with pytest.raises(NormalizationError, match="organization_series_code"):
        indicator_key(dataclasses.replace(DATASET, source=dataclasses.replace(DATASET.source, organization_series_code=None)))
    with pytest.raises(NormalizationError, match="no canonical unit"):
        normalize_who_dataset(dataclasses.replace(DATASET, unit=None), data(row()))


def test_provenance_names_the_request_and_keeps_the_source_fields():
    (observation,) = normalize_who_dataset(DATASET, data(row(Comments="a source note", Low=40.0, High=60.0, DataSourceDim="DS_X"))).observations
    assert observation.provenance == {
        "source_organization": "WHO",
        "source_indicator": "HWF_0001",
        "source_url": "https://ghoapi.azureedge.net/api/HWF_0001",
        "odata_context": "https://ghoapi.azureedge.net/api/$metadata#HWF_0001",
        "spatial_dim_type": "COUNTRY",
        "time_dim_type": "YEAR",
        "data_source_dim": "DS_X",
        "display_value": "50.5",
        "low": 40.0,
        "high": 60.0,
        "comments": "a source note",
        "source_date": "2001-02-03T04:05:06.7+01:00",
    }


def test_results_are_sorted_and_independent_of_row_order():
    rows = [row("USA", 2021), row("AUT", 2021), row("AUT", 2020)]
    forward = normalize_who_dataset(DATASET, data(*rows)).observations
    backward = normalize_who_dataset(DATASET, data(*reversed(rows))).observations
    assert [(o.country_code, o.year) for o in forward] == [("AUT", 2020), ("AUT", 2021), ("USA", 2021)] and forward == backward
