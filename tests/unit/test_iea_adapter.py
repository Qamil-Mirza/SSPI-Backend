"""IEA adapter: indicator key and row selection from canonical metadata, the
client, and the legacy cleaner semantics (pycountry geography, aggregates
skipped, null and zero values missing, year and value extraction, unit
check, duplicates). No network, no database."""

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.iea import BASE_URL, IEAClient, indicator_key, normalize_iea_dataset, read_rows
from sspi.ingestion.runner import SOURCES
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

PRODUCTS = {"IEA_TLCOAL": "COAL", "IEA_NATGAS": "NATGAS", "IEA_NCLEAR": "NUCLEAR", "IEA_HYDROP": "HYDRO", "IEA_GEOPWR": "GEOTHERM", "IEA_BIOWAS": "COMRENEW", "IEA_FSLOIL": "MTOTOIL"}


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(dimensions={"product": "COAL"}, query="TESbySource", unit="TJ", organization="IEA"):  # noqa: B006 - never mutated
    return DatasetMetadata(code="IEA_TEST", name="t", dataset_type="Intermediate", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, dimensions=dimensions))


def row(country="MYS", year="2022", value=1000310, product="COAL", units="TJ", short="MALAYSIA", **extra):
    return {"year": year, "short": short, "flow": "TES", "value": value, "flowLabel": "Total energy supply", "flowOrder": 7, "units": units, "product": product, "productLabel": "Coal and coal products", "productOrder": 1, "seriesLabel": "Coal and coal products", "country": country, **extra}


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_names_the_indicator_and_the_legacy_product_of_each_dataset(catalog):
    for code, product in PRODUCTS.items():
        canonical = catalog.dataset(code)
        assert indicator_key(canonical) == "TESbySource" and canonical.source.dimensions == {"product": product} and canonical.unit == "TJ"
        assert canonical.source.organization_series_code is None  # the legacy metadata had none; the product selects the series
    assert BASE_URL == "https://api.iea.org/stats/indicator/"
    assert catalog.dataset("IEA_GEOPWR").name == "Energy from Geothermal"  # legacy name kept; the product is solar, wind and other renewables (ALTNRG-1)


def test_indicator_key_requires_an_iea_dataset_with_a_query_a_selection_and_a_unit(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        indicator_key(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="query_code"):
        indicator_key(dataset(query=None))
    with pytest.raises(NormalizationError, match="dimensions"):
        indicator_key(dataset(dimensions=None))
    with pytest.raises(NormalizationError, match="unit"):
        indicator_key(dataset(unit=""))
    with pytest.raises(NormalizationError, match="no complete dataset definition"):
        indicator_key(catalog.dataset("WB_RAILNT"))


def test_the_adapter_is_tied_to_no_indicator_and_no_product():
    other = dataset(dimensions={"product": "TOTAL", "flow": "TRANSPORT"}, query="CO2BySector", unit="MtCO2")
    rows = [row(product="TOTAL", flow="TRANSPORT", units="MtCO2", value=54.2), row(product="TOTAL", flow="INDUSTRY", units="MtCO2", value=9.0)]
    result = normalize_iea_dataset(other, rows)
    assert [(o.dataset_code, o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("IEA_TEST", "MYS", 2022, 54.2, "MtCO2")]
    assert result.observations[0].provenance["source_indicator"] == "CO2BySector"
    assert SOURCES["IEA"].fetch_key(other) == "CO2BySector"  # one fetch per indicator, whatever it is


# --- normalizer ---------------------------------------------------------------------------------


def test_product_filter_year_value_unit_and_provenance():
    rows = [row(), row(year="1990", value=57000), row(country="AUT", short="AUSTRIA", value=110000), row(product="NATGAS", value=5)]
    result = normalize_iea_dataset(dataset(), rows)
    assert [(o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("AUT", 2022, 110000.0, "TJ"), ("MYS", 1990, 57000.0, "TJ"), ("MYS", 2022, 1000310.0, "TJ")]
    assert all(isinstance(o.value, float) for o in result.observations)
    assert dict(result.observations[2].provenance) == {
        "source_organization": "IEA",
        "source_indicator": "TESbySource",
        "source_area_name": "MALAYSIA",
        "source_dimensions": {"product": "COAL"},
        "flow": "TES",
        "flowLabel": "Total energy supply",
        "product": "COAL",
        "productLabel": "Coal and coal products",
        "seriesLabel": "Coal and coal products",
    }


def test_aggregates_and_names_that_are_not_iso3_codes_are_skipped_and_reported():
    rows = [row(), row(country="WORLD", short="WORLD"), row(country="EU27_2020", short="EU27_2020"), row(country="GUYANA", short="GUYANA"), row(country="XKX", short="KOSOVO")]
    result = normalize_iea_dataset(dataset(), rows)
    assert [o.country_code for o in result.observations] == ["MYS"]
    assert result.skipped_areas == (("EU27_2020", "EU27_2020"), ("GUYANA", "GUYANA"), ("WORLD", "WORLD"), ("XKX", "KOSOVO"))


def test_no_country_group_restriction_and_no_year_filter():
    result = normalize_iea_dataset(dataset(), [row(country="BOL", short="BOLIVIA", year="1990", value=1)])
    assert [(o.country_code, o.year) for o in result.observations] == [("BOL", 1990)]  # not an SSPI67 member, before 2000: kept


@pytest.mark.parametrize("value", [None, 0, 0.0, ""])
def test_null_and_zero_values_are_missing(value):
    """The legacy truthiness test (``if not value``) dropped a numeric zero as well; preserved."""
    result = normalize_iea_dataset(dataset(), [row(value=value), row(year="2021")])
    assert [o.year for o in result.observations] == [2021] and result.missing_values == 1


def test_missing_values_of_skipped_areas_are_not_counted():
    result = normalize_iea_dataset(dataset(), [row(country="WORLD", short="WORLD", value=None), row()])
    assert result.missing_values == 0 and len(result.observations) == 1


def test_malformed_rows_are_errors():
    with pytest.raises(NormalizationError, match="not a year"):
        normalize_iea_dataset(dataset(), [row(year="2022Q1")])
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize_iea_dataset(dataset(), [row(value="n/a")])
    with pytest.raises(NormalizationError, match="not finite"):
        normalize_iea_dataset(dataset(), [row(value="inf")])
    with pytest.raises(NormalizationError, match="disagrees with canonical unit"):
        normalize_iea_dataset(dataset(), [row(units="PJ")])
    with pytest.raises(NormalizationError, match="matched no rows"):
        normalize_iea_dataset(dataset(dimensions={"product": "PEAT"}), [row()])
    with pytest.raises(NormalizationError, match="expected a mapping"):
        normalize_iea_dataset(dataset(), ["x"])


def test_duplicates_are_refused():
    with pytest.raises(DuplicateObservationError, match=r"\(MYS, 2022\)"):
        normalize_iea_dataset(dataset(), [row(), row(value=2)])
    assert len(normalize_iea_dataset(dataset(), [row(), row(value=0)]).observations) == 1  # a dropped zero is not a duplicate


def test_rows_are_not_mutated():
    rows = [row(), row(value=None)]
    before = [dict(r) for r in rows]
    normalize_iea_dataset(dataset(), rows)
    assert rows == before


# --- client -------------------------------------------------------------------------------------


def test_client_requests_the_legacy_url_once():
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, json=[row(), row(year="2021")])

    with IEAClient(http=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        rows = client.fetch_indicator("TESbySource")
    assert requests == ["https://api.iea.org/stats/indicator/TESbySource"] and [r["year"] for r in rows] == ["2022", "2021"]  # no parameters, no key, no paging


def test_client_reports_http_failures_and_malformed_payloads():
    def client(response):
        return IEAClient(http=httpx.Client(transport=httpx.MockTransport(lambda request: response)))

    with pytest.raises(SourceRequestError, match="HTTP 403"):
        client(httpx.Response(403)).fetch_indicator("TESbySource")
    with pytest.raises(SourceResponseError, match="not JSON"):
        client(httpx.Response(200, content=b"<html>")).fetch_indicator("TESbySource")
    with pytest.raises(SourceResponseError, match="not a JSON array"):
        client(httpx.Response(200, json={"error": "moved"})).fetch_indicator("TESbySource")
    with pytest.raises(SourceResponseError, match="no rows"):
        client(httpx.Response(200, json=[])).fetch_indicator("NOPE")

    def refuse(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(SourceRequestError, match="failed"):
        IEAClient(http=httpx.Client(transport=httpx.MockTransport(refuse))).fetch_indicator("TESbySource")


def test_read_rows():
    assert read_rows([{"a": 1}], "X") == [{"a": 1}]
    with pytest.raises(SourceResponseError):
        read_rows([1, 2], "X")
