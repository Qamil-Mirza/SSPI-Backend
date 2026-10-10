"""UNESCO Institute for Statistics adapter: indicator key from canonical
metadata, the release-aware client, and the legacy cleaner semantics (ISO3
handling, null/NaN/falsy values missing, zeros dropped, year and value
extraction, canonical unit, provenance). No network, no database."""

import json
from pathlib import Path

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion import SOURCES, UISClient, normalize_uis_dataset
from sspi.ingestion.uis import BASE_URL, UISIndicatorData, indicator_key, read_response
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

FIXTURES = Path(__file__).parents[1] / "fixtures" / "uis"
DEFAULT = json.loads((FIXTURES / "versions_default.json").read_text())["version"]


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(series="NERT.1.CP", query="NERT.1.CP", unit="Percent", organization="UIS"):
    return DatasetMetadata(code="UIS_TEST", name="t", dataset_type="Indicator", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=series))


def record(geo="MYS", year=2021, value=87.9, indicator="NERT.1.CP", qualifier=None, magnitude=None):
    return {"indicatorId": indicator, "geoUnit": geo, "year": year, "value": value, "magnitude": magnitude, "qualifier": qualifier}


def data(*records, version="v1", indicator="NERT.1.CP"):
    return UISIndicatorData(indicator, version, tuple(records))


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_names_the_indicators(catalog):
    assert indicator_key(catalog.dataset("UIS_ENRPRI")) == "NERT.1.CP" == catalog.dataset("UIS_ENRPRI").source.organization_series_code
    assert indicator_key(catalog.dataset("UIS_ENRSEC")) == "NERT.2.CP" == catalog.dataset("UIS_ENRSEC").source.organization_series_code
    assert BASE_URL == "https://api.uis.unesco.org/api/public/" and "UIS" in SOURCES


def test_indicator_key_requires_a_uis_dataset_with_query_and_series(catalog):
    with pytest.raises(NormalizationError, match="'WB'"):
        indicator_key(catalog.dataset("WB_PUPTCH"))
    with pytest.raises(NormalizationError, match="query_code"):
        indicator_key(dataset(query=None))
    with pytest.raises(NormalizationError, match="organization_series_code"):
        indicator_key(dataset(series=None))


def test_the_adapter_is_not_specific_to_enrolment(catalog):
    years = dataset(series="YEARS.FC.COMP.1T3", query="YEARS.FC.COMP.1T3", unit="Years")
    result = normalize_uis_dataset(years, data(record(indicator="YEARS.FC.COMP.1T3", value=11), indicator="YEARS.FC.COMP.1T3"))
    assert [(o.dataset_code, o.country_code, o.year, o.value, o.unit) for o in result.observations] == [("UIS_TEST", "MYS", 2021, 11.0, "Years")]
    assert catalog.dataset("UIS_YRSEDU").source.query_code == "YEARS.FC.COMP.1T3" == indicator_key(catalog.dataset("UIS_YRSEDU"))


# --- normalizer ---------------------------------------------------------------------------------


def test_values_years_units_and_provenance():
    result = normalize_uis_dataset(dataset(), data(record("USA", 2022, 96.0177917480469, qualifier="NAT_EST"), record("AUT", "2021", "98.5"), version="20260507-91260335"))
    usa, aut = sorted(result.observations, key=lambda o: o.country_code, reverse=True)
    assert (usa.country_code, usa.year, usa.value, usa.unit) == ("USA", 2022, 96.0177917480469, "Percent")
    assert (aut.year, aut.value) == (2021, 98.5)  # string year and value parsed, as legacy int() / float() did
    assert dict(usa.provenance) == {"source_organization": "UIS", "source_indicator": "NERT.1.CP", "source_version": "20260507-91260335", "qualifier": "NAT_EST", "magnitude": None}
    assert [o.country_code for o in result.observations] == ["AUT", "USA"]  # sorted by identity


def test_null_nan_falsy_and_zero_values_are_missing_as_in_legacy():
    result = normalize_uis_dataset(dataset(), data(record("MYS", 2001, None), record("MYS", 2002, "NaN"), record("MYS", 2003, ""), record("MYS", 2004, 0), record("MYS", 2005, 0.0), record("MYS", 2006, 1.5)))
    assert [(o.year, o.value) for o in result.observations] == [(2006, 1.5)] and result.missing_values == 5


def test_non_iso3_areas_are_skipped_and_reported_without_a_country_filter():
    result = normalize_uis_dataset(dataset(), data(record("XKX"), record("SDG: Africa"), record("GLP", value=100), record("PRK", value=97.6)))
    assert result.skipped_areas == (("SDG: Africa", ""), ("XKX", ""))
    assert {o.country_code for o in result.observations} == {"GLP", "PRK"}  # territories and non-SSPI countries are kept


def test_bad_rows_are_errors_not_silently_dropped():
    with pytest.raises(NormalizationError, match="NERT.2.CP"):
        normalize_uis_dataset(dataset(), data(record(indicator="NERT.2.CP")))
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize_uis_dataset(dataset(), data(record(value="n/a")))
    with pytest.raises(NormalizationError, match="not a year"):
        normalize_uis_dataset(dataset(), data(record(year="2021-22", value=None)))  # legacy parsed the year first
    with pytest.raises(DuplicateObservationError, match=r"\(MYS, 2021\)"):
        normalize_uis_dataset(dataset(), data(record(), record(value=88.0)))


# --- client -------------------------------------------------------------------------------------


class Server:
    def __init__(self, records=None, hints=(), status=200):
        self.requests = []
        self.records = [record()] if records is None else records
        self.hints, self.status = list(hints), status

    def __call__(self, request):
        self.requests.append((request.url.path, dict(request.url.params)))
        if request.url.path.endswith("/versions/default"):
            return httpx.Response(200, content=(FIXTURES / "versions_default.json").read_bytes())
        return httpx.Response(self.status, json={"hints": self.hints, "records": self.records, "indicatorMetadata": []})

    def client(self, **kwargs):
        return UISClient(http=httpx.Client(transport=httpx.MockTransport(self)), **kwargs)


def test_default_release_is_resolved_once_and_requested_explicitly():
    server = Server()
    client = server.client()
    first, second = client.fetch_indicator("NERT.1.CP"), client.fetch_indicator("NERT.2.CP")
    assert server.requests == [
        ("/api/public/versions/default", {}),
        ("/api/public/data/indicators", {"indicator": "NERT.1.CP", "version": DEFAULT}),
        ("/api/public/data/indicators", {"indicator": "NERT.2.CP", "version": DEFAULT}),
    ]
    assert (first.indicator, first.version, first.records) == ("NERT.1.CP", DEFAULT, (record(),)) and second.version == DEFAULT


def test_a_selected_release_skips_the_default_lookup():
    server = Server()
    data_ = server.client(version="20260311-78618c3e").fetch_indicator("NERT.1.CP")
    assert server.requests == [("/api/public/data/indicators", {"indicator": "NERT.1.CP", "version": "20260311-78618c3e"})] and data_.version == "20260311-78618c3e"


def test_unknown_indicator_and_http_errors():
    with pytest.raises(SourceResponseError, match="could not be found"):
        Server(records=[], hints=[{"code": "UIS::HINT::001", "message": "The indicator could not be found, NOPE"}]).client().fetch_indicator("NOPE")
    with pytest.raises(SourceRequestError, match="HTTP 400"):
        Server(status=400).client().fetch_indicator("NERT.1.CP")
    assert read_response({"hints": [], "records": []}, "NERT.1.CP", "v").records == ()  # an empty answer without a hint is just empty
    with pytest.raises(SourceResponseError, match="no records list"):
        read_response([], "NERT.1.CP", "v")
