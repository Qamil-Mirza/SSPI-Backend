"""Tax Foundation CSV adapter: edition file from canonical metadata, the
checksum-pinned client, and the legacy cleaner semantics (wide-to-long,
iso_3 as published, missing tokens dropped, zeros kept, year from the column
name, canonical unit, provenance). No network, no database."""

import hashlib

import httpx
import pytest

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion import SOURCES, SUPPORTED_DATASETS, TaxFoundationClient, normalize_taxfoundation_dataset
from sspi.ingestion.taxfoundation import FILES, MISSING_TOKENS, SourceFile, TaxFoundationFile, file_key
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata

HEADER = '"","iso_2","iso_3","continent","country","2000","2001","2002"'
EDITION = FILES["rates_final_2025-01"]


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def dataset(query="rates_final_2025-01", organization="TF", unit="Tax Rate"):
    return DatasetMetadata(code="TF_TEST", name="t", dataset_type="Indicator", unit=unit, source=SourceMetadata(organization_code=organization, query_code=query, organization_series_code=None))


def downloaded(*rows, header=HEADER, key="rates_final_2025-01", newline="\r\n"):
    text = newline.join((header, *rows)) + newline
    return TaxFoundationFile(key, EDITION, hashlib.sha256(text.encode()).hexdigest(), text)


def normalize(*rows, **kwargs):
    return normalize_taxfoundation_dataset(dataset(), downloaded(*rows, **kwargs))


# --- metadata -----------------------------------------------------------------------------------


def test_canonical_metadata_names_the_2025_01_edition(catalog):
    source = catalog.dataset("TF_CRPTAX").source
    assert file_key(catalog.dataset("TF_CRPTAX")) == source.query_code == "rates_final_2025-01" and source.organization_code == "TF"
    assert EDITION == SourceFile("2025/01", "https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv", "7dd8f506e2942c816e28f01c7c478402fb39d3c263cf6c38b32f04df3fab9f52")
    assert list(FILES) == ["rates_final_2025-01"]  # one configured edition; nothing chooses a newer one
    assert "TF" in SOURCES and "TF_CRPTAX" in SUPPORTED_DATASETS and catalog.dataset("TF_CRPTAX").unit == "Tax Rate"
    assert EDITION.sha256 in source.note and EDITION.url in source.note


def test_file_key_requires_a_tax_foundation_dataset_with_a_query_code(catalog):
    with pytest.raises(NormalizationError, match="'WB'"):
        file_key(catalog.dataset("WB_TAXREV"))
    with pytest.raises(NormalizationError, match="query_code"):
        file_key(dataset(query=None))


# --- normalizer ---------------------------------------------------------------------------------


def test_wide_rows_become_one_observation_per_valued_year_with_provenance():
    file = downloaded('"1","MY","MYS","AS","Malaysia",28,"27",26.5', '"2","AT","AUT","EU","Austria",34,NA,34')
    FILE_SHA = file.sha256
    result = normalize('"1","MY","MYS","AS","Malaysia",28,"27",26.5', '"2","AT","AUT","EU","Austria",34,NA,34')
    assert [(o.country_code, o.year, o.value, o.unit) for o in result.observations] == [
        ("AUT", 2000, 34.0, "Tax Rate"),
        ("AUT", 2002, 34.0, "Tax Rate"),
        ("MYS", 2000, 28.0, "Tax Rate"),
        ("MYS", 2001, 27.0, "Tax Rate"),
        ("MYS", 2002, 26.5, "Tax Rate"),
    ]
    assert result.missing_values == 1 and result.skipped_areas == ()
    assert dict(result.observations[0].provenance) == {
        "source_organization": "TF",
        "source_file": "rates_final_2025-01",
        "source_edition": "2025/01",
        "source_url": EDITION.url,
        "source_sha256": FILE_SHA,
        "source_country_name": "Austria",
        "source_value": "34",
    }


def test_zeros_are_values_and_every_pandas_missing_token_is_missing():
    result = normalize('"1","BH","BHR","AS","Bahrain",0,0.0,NA', '"2","XK","XKX","EU","Kosovo",,N/A,10')
    assert [(o.country_code, o.year, o.value) for o in result.observations] == [("BHR", 2000, 0.0), ("BHR", 2001, 0.0), ("XKX", 2002, 10.0)]
    assert result.missing_values == 3
    assert {"NA", "", "N/A", "NaN", "null"} <= MISSING_TOKENS and "0" not in MISSING_TOKENS


def test_areas_are_kept_as_published_without_an_iso_check():
    result = normalize('"1","AN","ANT","NO","Netherlands Antilles",34,NA,NA', '"2","NA","NAM","AF","Namibia",NA,40,40', '"3","KP","PRK","AS","North Korea",NA,NA,NA')
    assert {o.country_code for o in result.observations} == {"ANT", "NAM"}  # Namibia's iso_2 is "NA" and is ignored
    assert result.missing_values == 2 + 1 + 3  # an all-NA area simply has no observation


def test_a_row_with_a_missing_iso3_is_skipped_as_legacy_dropna_did():
    result = normalize('"1","","NA","XX","Nowhere",10,10,10', '"2","MY","MYS","AS","Malaysia",28,NA,NA')
    assert result.skipped_areas == (("NA", "Nowhere"),) and [o.country_code for o in result.observations] == ["MYS"]


def test_line_endings_do_not_matter():
    def values(result):
        return [(o.country_code, o.year, o.value, o.provenance["source_value"]) for o in result.observations]

    assert values(normalize('"1","MY","MYS","AS","Malaysia",28,27,26', newline="\n")) == values(normalize('"1","MY","MYS","AS","Malaysia",28,27,26'))  # only the checksum differs


def test_bad_files_are_errors_not_silently_repaired():
    with pytest.raises(DuplicateObservationError, match="MYS has more than one row"):
        normalize('"1","MY","MYS","AS","Malaysia",28,27,26', '"2","MY","MYS","AS","Malaysia",1,1,1')
    with pytest.raises(NormalizationError, match="not numeric"):
        normalize('"1","MY","MYS","AS","Malaysia",28,n.a.,26')
    with pytest.raises(NormalizationError, match="'notes' is not a year"):
        normalize('"1","MY","MYS","AS","Malaysia",28,27,26,x', header=HEADER + ',"notes"')
    with pytest.raises(NormalizationError, match=r"lacks columns \['continent'\]"):
        normalize('"1","MY","MYS","Malaysia",28,27,26', header='"","iso_2","iso_3","country","2000","2001","2002"')
    with pytest.raises(NormalizationError, match="has 7 fields"):
        normalize('"1","MY","MYS","AS","Malaysia",28,27')
    with pytest.raises(NormalizationError, match="not the dataset's"):
        normalize_taxfoundation_dataset(dataset(), downloaded('"1","MY","MYS","AS","Malaysia",28,27,26', key="rates_final_2024"))


# --- client -------------------------------------------------------------------------------------


class Server:
    def __init__(self, content=b"a,b\r\n", status=200):
        self.content, self.status, self.requests = content, status, []

    def __call__(self, request):
        self.requests.append(str(request.url))
        return httpx.Response(self.status, content=self.content, headers={"content-type": "text/csv"})

    def client(self, **kwargs):
        return TaxFoundationClient(http=httpx.Client(transport=httpx.MockTransport(self)), **kwargs)


def pinned(content, url="https://example.org/rates.csv"):
    return {"rates_test": SourceFile("test", url, hashlib.sha256(content).hexdigest())}


def test_the_configured_file_is_fetched_once_and_its_checksum_verified():
    server = Server(b"x,y\r\n1,2\r\n")
    file = server.client(files=pinned(server.content)).fetch_file("rates_test")
    assert server.requests == ["https://example.org/rates.csv"] and file.text == "x,y\r\n1,2\r\n" and file.source.edition == "test"
    assert file.sha256 == hashlib.sha256(server.content).hexdigest()


def test_changed_content_is_refused_and_nothing_else_is_tried():
    server = Server(b"different\r\n")
    with pytest.raises(SourceResponseError, match="no other edition is substituted"):
        server.client(files=pinned(b"expected\r\n")).fetch_file("rates_test")
    assert len(server.requests) == 1


def test_the_default_client_reads_the_approved_edition_and_refuses_anything_else():
    server = Server(b"not the 2025/01 file")
    with pytest.raises(SourceResponseError, match="2025/01"):
        server.client().fetch_file("rates_final_2025-01")
    assert server.requests == [EDITION.url]


def test_an_explicitly_unpinned_location_accepts_any_content():
    server = Server(b"x\r\n")
    assert server.client(files={"k": SourceFile("draft", "https://example.org/k.csv", None)}).fetch_file("k").text == "x\r\n"


def test_unknown_files_and_http_errors():
    with pytest.raises(SourceRequestError, match="no Tax Foundation file is configured for 'rates_final'"):
        Server().client().fetch_file("rates_final")  # the legacy query code names no edition
    with pytest.raises(SourceRequestError, match="HTTP 404"):
        Server(status=404).client().fetch_file("rates_final_2025-01")
