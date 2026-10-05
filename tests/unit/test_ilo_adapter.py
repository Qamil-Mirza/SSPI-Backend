"""ILO adapter: the request from canonical metadata, the SDMX client and its
legacy time windows, and the legacy cleaner semantics (dimension filters,
aggregate areas skipped, null values missing, zero kept, year and value
extraction, canonical unit, attributes in provenance). No network, no
database."""

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.ilo import BASE_URL, REQUEST_PERIODS, ILOClient, normalize_ilo_dataset, parse_query, query_key, read_message
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

QUERY = "Indicator=DF_TEST_RT;Parameters=.A..SEX_T"


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(query=QUERY, series="DF_TEST_RT", dimensions=None, unit="Rate", organization="ILO"):
    return DatasetMetadata(
        code="ILO_TEST", name="t", dataset_type="Indicator", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=series, dimensions=dimensions)
    )


AREAS = [{"id": "MYS", "name": "Malaysia"}, {"id": "AUT", "name": "Austria"}, {"id": "X01", "name": "World"}, {"id": "KOS", "name": "Kosovo"}]
SEXES = [{"id": "SEX_T", "name": "Total"}, {"id": "SEX_F", "name": "Female"}]
YEARS = [{"id": "2021"}, {"id": "2019"}, {"id": "2020"}]


def message(series, *, years=YEARS, sexes=SEXES):
    """An SDMX-JSON data message: ``series`` maps "area:freq:sex" index keys to {time index: cells}."""
    return {
        "data": {
            "structures": [
                {
                    "dimensions": {
                        "series": [  # deliberately not in keyPosition order
                            {"id": "SEX", "keyPosition": 2, "values": sexes},
                            {"id": "REF_AREA", "keyPosition": 0, "values": AREAS},
                            {"id": "FREQ", "keyPosition": 1, "values": [{"id": "A", "name": "Annual"}]},
                        ],
                        "observation": [{"id": "TIME_PERIOD", "values": years}],
                    },
                    "attributes": {
                        "series": [{"id": "UNIT_MEASURE", "values": [{"id": "PT"}]}],
                        "observation": [{"id": "SOURCE", "values": [{"value": "LFS - Labour Force Survey"}]}, {"id": "OBS_STATUS", "values": [{"id": "B", "name": "Break in series"}]}],
                    },
                }
            ],
            "dataSets": [{"series": {key: {"attributes": [0], "observations": observations} for key, observations in series.items()}}],
        }
    }


def rows(result):
    return [(o.country_code, o.year, o.value, o.unit) for o in result.observations]


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_names_the_request_the_dataflow_and_the_filters(catalog):
    employ, colbar = catalog.dataset("ILO_EMPLOY_TO_POP"), catalog.dataset("ILO_COLBAR")
    assert query_key(employ) == "Indicator=DF_EMP_DWAP_SEX_AGE_RT;Parameters=.A..SEX_T.AGE_YTHADULT_Y15-64"
    assert parse_query(query_key(employ)) == ("DF_EMP_DWAP_SEX_AGE_RT", ".A..SEX_T.AGE_YTHADULT_Y15-64") and employ.source.organization_series_code == "DF_EMP_DWAP_SEX_AGE_RT"
    assert employ.source.dimensions == {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_Y15-64"} and employ.unit == "Rate"
    assert parse_query(query_key(colbar)) == ("DF_ILR_CBCT_NOC_RT", "") and colbar.source.dimensions is None and colbar.unit == "Proportion"
    assert set(REQUEST_PERIODS) == {query_key(employ), query_key(colbar)}  # the legacy collectors' time windows
    assert BASE_URL == "https://sdmx.ilo.org/rest/data/"


def test_query_key_requires_an_ilo_dataset_with_a_well_formed_query(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        query_key(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="query_code"):
        query_key(dataset(query=None))
    with pytest.raises(NormalizationError, match="not of the form"):
        query_key(dataset(query="DF_TEST_RT"))
    with pytest.raises(NormalizationError, match="not of the form"):
        query_key(dataset(query="Indicator=;Parameters="))
    with pytest.raises(NormalizationError, match="names dataflow 'DF_OTHER'"):
        query_key(dataset(series="DF_OTHER"))
    with pytest.raises(NormalizationError, match="no complete dataset definition"):
        query_key(catalog.dataset("WB_RAILNT"))


# --- normalizer ---------------------------------------------------------------------------------


def test_area_year_value_and_canonical_unit():
    result = normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": [66.5, 0, None], "1": [65, None, 0]}, "1:0:0": {"2": [73.8, None, None]}}))
    assert rows(result) == [("AUT", 2020, 73.8, "Rate"), ("MYS", 2019, 65.0, "Rate"), ("MYS", 2021, 66.5, "Rate")]  # sorted; the time index is a position, not a year
    assert all(isinstance(o.value, float) and isinstance(o.year, int) for o in result.observations)
    assert result.skipped_areas == () and result.missing_values == 0
    assert dict(result.observations[2].provenance) == {
        "source_organization": "ILO",
        "source_dataflow": "DF_TEST_RT",
        "source_query": QUERY,
        "source_area_name": "Malaysia",
        "FREQ": "A",
        "SEX": "SEX_T",
        "UNIT_MEASURE": "PT",
        "SOURCE": "LFS - Labour Force Survey",
    }
    assert result.observations[1].provenance["OBS_STATUS"] == "B" and "SOURCE" not in result.observations[1].provenance  # flags kept, never filtered


def test_canonical_dimensions_select_the_series_exactly():
    payload = message({"0:0:0": {"0": [66.5]}, "0:0:1": {"0": [51.2]}})
    assert rows(normalize_ilo_dataset(dataset(dimensions={"SEX": "SEX_T"}), payload)) == [("MYS", 2021, 66.5, "Rate")]
    assert rows(normalize_ilo_dataset(dataset(dimensions={"SEX": "SEX_F"}), payload)) == [("MYS", 2021, 51.2, "Rate")]
    with pytest.raises(DuplicateObservationError, match=r"duplicate \(MYS, 2021\).*do not select one series"):
        normalize_ilo_dataset(dataset(), payload)  # no filter: two series for one identity is an error, never a silent pick
    with pytest.raises(NormalizationError, match=r"\['AGE'\] are not series dimensions"):
        normalize_ilo_dataset(dataset(dimensions={"AGE": "AGE_YTHADULT_Y15-64"}), payload)


def test_aggregate_areas_are_skipped_and_reported_and_other_codes_are_kept_as_the_source_codes_them():
    result = normalize_ilo_dataset(dataset(), message({"2:0:0": {"0": [57.0]}, "3:0:0": {"0": [30.1]}, "0:0:0": {"0": [66.5]}}))
    assert rows(result) == [("KOS", 2021, 30.1, "Rate"), ("MYS", 2021, 66.5, "Rate")]  # KOS is not ISO 3166-1; legacy kept it
    assert result.skipped_areas == (("X01", "World"),)  # a code with a digit is an ILO aggregate


def test_null_is_missing_and_zero_is_a_value():
    result = normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": [None, 0, None], "1": [0, None, None], "2": []}}))
    assert rows(result) == [("MYS", 2019, 0.0, "Rate")] and result.missing_values == 2


def test_malformed_content_fails_instead_of_being_dropped():
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": ["n/a"]}}))
    with pytest.raises(NormalizationError, match="not finite"):
        normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": [float("inf")]}}))
    with pytest.raises(NormalizationError, match="TIME_PERIOD that is a year"):
        normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": [1.0]}}, years=[{"id": "2021-Q1"}]))
    with pytest.raises(NormalizationError, match="TIME_PERIOD that is a year"):
        normalize_ilo_dataset(dataset(), message({"0:0:0": {"7": [1.0]}}))
    with pytest.raises(NormalizationError, match="series key does not match"):
        normalize_ilo_dataset(dataset(), message({"0:0": {"0": [1.0]}}))
    with pytest.raises(NormalizationError, match="series key does not match"):
        normalize_ilo_dataset(dataset(), message({"9:0:0": {"0": [1.0]}}))
    with pytest.raises(NormalizationError, match="attribute 'SOURCE' has no value at index 5"):
        normalize_ilo_dataset(dataset(), message({"0:0:0": {"0": [1.0, 5]}}))
    with pytest.raises(SourceResponseError, match="not an SDMX-JSON data message"):
        normalize_ilo_dataset(dataset(), {"errors": []})
    broken = message({})
    broken["data"]["structures"][0]["dimensions"]["series"] = [d for d in broken["data"]["structures"][0]["dimensions"]["series"] if d["id"] != "REF_AREA"]
    with pytest.raises(NormalizationError, match="no REF_AREA dimension"):
        normalize_ilo_dataset(dataset(), broken)


def test_an_empty_message_is_no_observations():
    result = normalize_ilo_dataset(dataset(), message({}))
    assert result.observations == [] and result.skipped_areas == () and result.missing_values == 0


# --- client -------------------------------------------------------------------------------------


def client(handler):
    return ILOClient(http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_client_requests_the_dataflow_and_key_with_the_legacy_time_window(catalog):
    seen = []

    def handler(request):
        seen.append((str(request.url).split("?")[0], dict(request.url.params)))
        return httpx.Response(200, json=message({}))

    with client(handler) as ilo:
        ilo.fetch_query(query_key(catalog.dataset("ILO_EMPLOY_TO_POP")))
        ilo.fetch_query(query_key(catalog.dataset("ILO_COLBAR")))
        ilo.fetch_query(QUERY)
    assert seen == [
        ("https://sdmx.ilo.org/rest/data/DF_EMP_DWAP_SEX_AGE_RT/.A..SEX_T.AGE_YTHADULT_Y15-64", {"format": "jsondata", "startPeriod": "2000"}),
        ("https://sdmx.ilo.org/rest/data/DF_ILR_CBCT_NOC_RT", {"format": "jsondata", "startPeriod": "1990-01-01", "endPeriod": "2024-12-31"}),
        ("https://sdmx.ilo.org/rest/data/DF_TEST_RT/.A..SEX_T", {"format": "jsondata"}),  # no recorded window: none sent
    ]


def test_client_errors_are_source_errors():
    with client(lambda request: httpx.Response(503)) as ilo, pytest.raises(SourceRequestError, match="HTTP 503"):
        ilo.fetch_query(QUERY)
    with client(lambda request: httpx.Response(200, content=b"<html>")) as ilo, pytest.raises(SourceResponseError, match="not JSON"):
        ilo.fetch_query(QUERY)
    with client(lambda request: httpx.Response(200, json={"data": {}})) as ilo, pytest.raises(SourceResponseError, match="not an SDMX-JSON data message"):
        ilo.fetch_query(QUERY)

    def refuse(request):
        raise httpx.ConnectError("no route")

    with client(refuse) as ilo, pytest.raises(SourceRequestError, match="no route"):
        ilo.fetch_query(QUERY)


def test_an_injected_http_client_is_not_closed():
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=message({}))))
    with ILOClient(http=http):
        pass
    assert not http.is_closed
    http.close()
    owned = ILOClient()
    owned.close()
    assert owned.http.is_closed


def test_read_message_returns_structure_and_data_sets():
    payload = message({"0:0:0": {"0": [1.0]}})
    structure, data_sets = read_message(payload, "t")
    assert structure is payload["data"]["structures"][0] and data_sets is payload["data"]["dataSets"]
    for bad in (None, [], {"data": None}, {"data": {"dataSets": [], "structures": []}}):
        with pytest.raises(SourceResponseError):
            read_message(bad, "t")
