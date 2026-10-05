"""FAOSTAT bulk adapter: query parsing, bulk-file reading, the pure normalizer
and its legacy cleaner semantics, on the committed bulk-file sample."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.fao import DOMAIN_ARTIFACTS, FAOBulkClient, SourceFilters, normalize_fao_dataset, read_bulk_archive, read_bulk_csv, source_filters
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

FIXTURE = Path(__file__).parents[1] / "fixtures" / "fao" / "Inputs_LandUse_E_All_Data_(Normalized)_sample.csv"


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


@pytest.fixture(scope="module")
def rows():
    return read_bulk_csv(FIXTURE.read_text(encoding="utf-8"), "RL")


def dataset(code="UNFAO_TEST", unit="1000 ha", query="Domain=RL;Element=5110;Item=6717", organization="UNFAO"):
    return DatasetMetadata(code=code, name=code, dataset_type="Intermediate", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query))


# --- source identifiers ---------------------------------------------------------------


def test_query_code_encodes_domain_element_and_item(catalog):
    assert source_filters(catalog.dataset("UNFAO_FRSTLV")) == SourceFilters("RL", "5110", "6717")
    assert source_filters(catalog.dataset("UNFAO_CRBNLV")) == SourceFilters("RL", "72151", "6646")  # bulk element code; legacy API used 7215 (PROVENANCE.yaml)
    assert source_filters(catalog.dataset("UNFAO_FRSTAV")) == source_filters(catalog.dataset("UNFAO_FRSTLV"))
    assert source_filters(catalog.dataset("UNFAO_CRBNAV")) == source_filters(catalog.dataset("UNFAO_CRBNLV"))


@pytest.mark.parametrize("bad", ["", "RL;5110;6717", "Domain=RL;Element=x;Item=6717", "Element=5110;Item=6717;Domain=RL"])
def test_malformed_query_codes_are_rejected(bad):
    with pytest.raises(NormalizationError, match="query_code"):
        source_filters(dataset(query=bad))


def test_other_organizations_and_incomplete_definitions_are_rejected(catalog):
    with pytest.raises(NormalizationError, match="UNSDG"):
        source_filters(catalog.dataset("UNSDG_MARINE"))
    with pytest.raises(NormalizationError, match="no complete dataset definition"):
        source_filters(catalog.dataset("IMF_FSTABL"))


# --- bulk file reading -------------------------------------------------------------------


def test_bulk_csv_rows_keep_the_source_header(rows):
    assert len(rows) == 2777 and rows[0]["Area Code (M49)"] == "'008" and rows[0]["Unit"] == "1000 ha"


def test_bulk_csv_header_must_carry_every_column_read():
    with pytest.raises(SourceResponseError, match="Value"):
        read_bulk_csv("Area Code,Area\n1,World\n")


def test_bulk_archive_is_the_single_normalized_csv_member():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Inputs_LandUse_E_All_Data_(Normalized).csv", "﻿" + FIXTURE.read_text(encoding="utf-8"))
        z.writestr("Inputs_LandUse_E_Flags.csv", "Flag,Description\nA,Official value\n")
    assert len(read_bulk_archive(buffer.getvalue(), "RL")) == 2777
    with pytest.raises(SourceResponseError, match="not a zip"):
        read_bulk_archive(b"<html>not a zip</html>", "RL")
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("other.csv", "a\n")
    with pytest.raises(SourceResponseError, match="expected one"):
        read_bulk_archive(empty.getvalue(), "RL")


def test_client_downloads_the_registered_domain_artifact_once_per_call():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Inputs_LandUse_E_All_Data_(Normalized).csv", FIXTURE.read_text(encoding="utf-8"))
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=buffer.getvalue())

    with FAOBulkClient(http=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        assert len(client.fetch_domain("RL")) == 2777
    assert requested == ["https://bulks-faostat.fao.org/production/" + DOMAIN_ARTIFACTS["RL"]]


def test_client_reports_unknown_domains_and_http_failures():
    def handler(request):
        return httpx.Response(503)

    with FAOBulkClient(http=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        with pytest.raises(SourceRequestError, match="HTTP 503"):
            client.fetch_domain("RL")
        with pytest.raises(SourceRequestError, match="no FAOSTAT bulk artifact"):
            client.fetch_domain("QCL")


# --- normalizer --------------------------------------------------------------------------


def test_selects_the_element_and_item_and_maps_m49_to_iso3(catalog, rows):
    result = normalize_fao_dataset(catalog.dataset("UNFAO_FRSTLV"), rows)
    assert {o.dataset_code for o in result.observations} == {"UNFAO_FRSTLV"}
    assert {o.unit for o in result.observations} == {"1000 ha"}
    countries = {o.country_code for o in result.observations}
    assert "CHN" in countries and "KWT" not in countries and "ARE" in countries  # Kuwait has no naturally regenerating forest rows
    chn = {o.year: o for o in result.observations if o.country_code == "CHN"}
    assert chn[2000].provenance["source_area_name"] == "China, mainland" and chn[2000].provenance["source_m49_code"] == "156"
    assert result.observations == sorted(result.observations, key=lambda o: (o.country_code, o.year))


def test_aggregates_and_non_m49_countries_are_skipped_and_reported(catalog, rows):
    result = normalize_fao_dataset(catalog.dataset("UNFAO_FRSTLV"), rows)
    assert set(result.skipped_areas) == {("5000", "World"), ("5400", "Europe"), ("351", "China"), ("15", "Belgium-Luxembourg")}


def test_empty_values_are_missing_and_zero_values_are_kept(catalog, rows):
    forest = normalize_fao_dataset(catalog.dataset("UNFAO_FRSTLV"), rows)
    assert forest.missing_values == 3  # Nicaragua 2023-2025, flag L
    assert not any(o.country_code == "NIC" and o.year >= 2023 for o in forest.observations)
    carbon = normalize_fao_dataset(catalog.dataset("UNFAO_CRBNLV"), rows)
    greenland = {o.year: o.value for o in carbon.observations if o.country_code == "GRL"}
    assert len(greenland) == 36 and greenland[1991] == 0.0 and greenland[1990] == 0.0026  # zeros are observations, not missing


def test_flags_are_preserved_in_provenance_and_never_filter(catalog, rows):
    result = normalize_fao_dataset(catalog.dataset("UNFAO_CRBNLV"), rows)
    flags = {o.provenance["flag"] for o in result.observations}
    assert {"I", "X"} <= flags
    first = result.observations[0]
    assert first.provenance["source_domain"] == "RL" and first.provenance["source_element_code"] == "72151" and first.provenance["source_item_code"] == "6646"
    assert first.provenance["source_element"] == "Carbon stock in living biomass" and first.provenance["source_item"] == "Forest land"


def test_unit_must_match_the_canonical_unit(rows):
    with pytest.raises(NormalizationError, match="disagrees with canonical unit"):
        normalize_fao_dataset(dataset(unit="ha"), rows)


def test_absent_series_is_an_error_listing_what_is_present(rows):
    with pytest.raises(NormalizationError, match=r"no rows for element 9999.*\('5110', '6646'\)"):
        normalize_fao_dataset(dataset(query="Domain=RL;Element=9999;Item=6717"), rows)


def test_two_areas_mapping_to_one_country_collide():
    base = {"Item Code": "6717", "Element Code": "5110", "Year": "2000", "Unit": "1000 ha", "Value": "1.000000", "Flag": "A", "Element": "Area", "Item": "x", "Note": ""}
    collision = [
        {**base, "Area Code": "41", "Area Code (M49)": "'156", "Area": "China, mainland"},
        {**base, "Area Code": "999", "Area Code (M49)": "156", "Area": "China again"},
    ]
    with pytest.raises(DuplicateObservationError, match="CHN"):
        normalize_fao_dataset(dataset(), collision)


@pytest.mark.parametrize("value", ["abc", "inf", "nan"])
def test_non_numeric_values_are_errors(value):
    row = {"Area Code": "11", "Area Code (M49)": "'040", "Area": "Austria", "Item Code": "6717", "Element Code": "5110", "Year": "2000", "Unit": "1000 ha", "Value": value, "Flag": "A", "Element": "Area", "Item": "x"}
    with pytest.raises(NormalizationError, match="not (numeric|finite)"):
        normalize_fao_dataset(dataset(), [row])


def test_rows_are_not_mutated(catalog, rows):
    before = [dict(r) for r in rows]
    normalize_fao_dataset(catalog.dataset("UNFAO_FRSTLV"), rows)
    assert [dict(r) for r in rows] == before
