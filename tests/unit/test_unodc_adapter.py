"""The UNODC workbook client and the normalizer's guards, on the committed
synthetic workbook served by a mock transport. No network."""

import hashlib

import httpx
import pytest

from sspi.errors import NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.unodc import WORKBOOKS, SourceWorkbook, UNODCWorkbook, UNODCWorkbookClient, normalize_unodc_dataset, workbook_key
from sspi.metadata import MetadataCatalog
from tests.golden.public_safety import UNODC_KEY, UNODC_WORKBOOK

CATALOG = MetadataCatalog.load()
SYNTHETIC = UNODC_WORKBOOK.read_bytes()


def client(handler, workbooks=None):
    return UNODCWorkbookClient(workbooks=workbooks, http=httpx.Client(transport=httpx.MockTransport(handler)))


def pinned_to_synthetic():
    return {UNODC_KEY: SourceWorkbook("synthetic", WORKBOOKS[UNODC_KEY].url, hashlib.sha256(SYNTHETIC).hexdigest())}


def test_the_default_table_pins_the_portal_release():
    source = WORKBOOKS[UNODC_KEY]
    assert source.url == "https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_prisons_and_prisoners.xlsx"
    assert source.sha256 == "27f6a3bbc89769a9acef0675335b9ca4dca7ec3776db9499127256d39b7e14e6" and source.retrieved == "2026-10-25"
    assert workbook_key(CATALOG.dataset("UNODC_PRIPOP")) == UNODC_KEY


def test_a_pinned_download_is_returned_with_its_checksum():
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=SYNTHETIC)

    with client(handler, pinned_to_synthetic()) as c:
        workbook = c.fetch_workbook(UNODC_KEY)
    assert requested == [WORKBOOKS[UNODC_KEY].url] and workbook.content == SYNTHETIC and workbook.sha256 == hashlib.sha256(SYNTHETIC).hexdigest()


def test_other_bytes_at_the_pinned_address_are_refused():
    with client(lambda request: httpx.Response(200, content=SYNTHETIC)) as c, pytest.raises(SourceResponseError, match="no other edition is substituted"):
        c.fetch_workbook(UNODC_KEY)  # the synthetic bytes are not the pinned release


def test_http_failures_and_unknown_keys_are_request_errors():
    with client(lambda request: httpx.Response(404)) as c, pytest.raises(SourceRequestError, match="HTTP 404"):
        c.fetch_workbook(UNODC_KEY)
    with client(lambda request: httpx.Response(200)) as c, pytest.raises(SourceRequestError, match="no UNODC workbook is configured"):
        c.fetch_workbook("data_cts_prisons_and_prisoners")  # the legacy file name alone names no edition


def test_an_html_page_instead_of_a_workbook_is_refused():
    """The retired legacy address now answers with the portal's home page."""
    page = b"<!DOCTYPE html><html><title>Data Portal UNODC</title></html>"
    workbook = UNODCWorkbook(UNODC_KEY, SourceWorkbook("page", "x", None), hashlib.sha256(page).hexdigest(), page)
    with pytest.raises(SourceResponseError, match="not a readable Excel file"):
        normalize_unodc_dataset(CATALOG.dataset("UNODC_PRIPOP"), workbook)


def test_a_workbook_for_another_key_is_refused():
    workbook = UNODCWorkbook("other", SourceWorkbook("x", "x", None), "x", SYNTHETIC)
    with pytest.raises(NormalizationError, match="is not the dataset's"):
        normalize_unodc_dataset(CATALOG.dataset("UNODC_PRIPOP"), workbook)
