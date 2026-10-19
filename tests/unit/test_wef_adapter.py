"""The WEF workbook client and normalizer on the committed synthetic workbook
and messages written here (not WEF data): the pinned edition, explicitly
configured alternatives, request failures, metadata-driven series selection
and the cases the legacy parity fixture does not reach. No network."""

import dataclasses
import hashlib
from pathlib import Path

import httpx
import pytest

from sspi.errors import NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion import SOURCES, WEFWorkbookClient, normalize_wef_dataset
from sspi.ingestion.wef import WORKBOOKS, SourceWorkbook, WEFWorkbook, legacy_unit, workbook_key
from sspi.metadata import MetadataCatalog

CATALOG = MetadataCatalog.load()
DATASET = CATALOG.dataset("WEF_QUELEC")
KEY = "WEF-GCIHH_2023-07-17"
CONTENT = (Path(__file__).parents[1] / "fixtures" / "wef" / "WEF-GCIHH_synthetic.xlsx").read_bytes()
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def client(handler, **kwargs):
    return WEFWorkbookClient(http=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)


def with_source(**changes):
    return dataclasses.replace(DATASET, source=dataclasses.replace(DATASET.source, **changes))


# --- client ------------------------------------------------------------------------------------


def test_the_default_edition_is_the_legacy_workbook_pinned_by_checksum():
    source = WORKBOOKS[KEY]
    assert source.url == "https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx"
    assert source.sha256 == "a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451" and source.retrieved == "2026-10-19"
    assert "2023-07-17" in source.edition and "2007-2017" in source.edition and list(WORKBOOKS) == [KEY]
    assert workbook_key(DATASET) == KEY and SOURCES["WEF"].fetch_key(DATASET) == KEY


def test_a_download_with_other_bytes_is_refused_even_at_the_same_address():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=CONTENT)  # the synthetic workbook, not the pinned one

    with pytest.raises(SourceResponseError, match="no other edition is substituted"):
        client(handler).fetch_workbook(KEY)
    assert seen == [WORKBOOKS[KEY].url]


def test_an_explicitly_configured_edition_is_read_and_recorded():
    alternative = {KEY: SourceWorkbook("synthetic test edition", "https://example.invalid/WEF-GCIHH.xlsx", DIGEST)}
    fetched = client(lambda request: httpx.Response(200, content=CONTENT), workbooks=alternative).fetch_workbook(KEY)
    assert (fetched.key, fetched.sha256, fetched.source.edition) == (KEY, DIGEST, "synthetic test edition")
    (observation, *_) = normalize_wef_dataset(DATASET, fetched).observations
    assert observation.provenance["source_url"] == "https://example.invalid/WEF-GCIHH.xlsx" and observation.provenance["source_edition"] == "synthetic test edition"
    assert WORKBOOKS[KEY].url != alternative[KEY].url  # the default table is untouched


def test_an_unpinned_location_must_be_configured_explicitly():
    unpinned = {KEY: SourceWorkbook("unpinned", "https://example.invalid/x.xlsx", None)}
    assert client(lambda request: httpx.Response(200, content=b"anything"), workbooks=unpinned).fetch_workbook(KEY).sha256 == hashlib.sha256(b"anything").hexdigest()


@pytest.mark.parametrize(("response", "error", "match"), [(httpx.Response(404), SourceRequestError, "HTTP 404"), (httpx.Response(503), SourceRequestError, "HTTP 503")])
def test_request_failures_are_reported(response, error, match):
    with pytest.raises(error, match=match):
        client(lambda request: response).fetch_workbook(KEY)


def test_an_unknown_workbook_and_a_network_failure_are_reported():
    with pytest.raises(SourceRequestError, match="no WEF workbook is configured"):
        client(lambda request: httpx.Response(200)).fetch_workbook("WEF-GCIHH_2030-01-01")

    def fail(request):
        raise httpx.ConnectError("unreachable")

    with pytest.raises(SourceRequestError, match="failed"):
        client(fail).fetch_workbook(KEY)


def test_an_injected_http_client_is_not_closed_and_an_owned_one_is():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with WEFWorkbookClient(http=http):
        pass
    assert not http.is_closed
    http.close()
    with WEFWorkbookClient() as owned:
        pass
    assert owned.http.is_closed


# --- normalizer --------------------------------------------------------------------------------


def synthetic():
    return WEFWorkbook(KEY, WORKBOOKS[KEY], DIGEST, CONTENT)


def test_the_series_and_the_attribute_come_from_metadata():
    roads = normalize_wef_dataset(with_source(organization_series_code="WEF.GCIHH.EOSQ065"), synthetic())
    assert {o.value for o in roads.observations} == {2.5} and len(roads.observations) == 7 * 11  # every economy's road row
    with pytest.raises(NormalizationError, match="is not the canonical unit"):
        normalize_wef_dataset(dataclasses.replace(DATASET, unit="Rank"), synthetic())  # the unit derived from the indicator name must match
    ranks = normalize_wef_dataset(with_source(dimensions={"Attribute 1": "Rank"}), synthetic())
    assert all(o.value >= 10 for o in ranks.observations)  # the Rank rows, when metadata asks for them
    with pytest.raises(NormalizationError, match="lacks columns"):
        normalize_wef_dataset(with_source(dimensions={"Attribute 9": "Value"}), synthetic())


def test_metadata_must_name_the_workbook_the_series_and_the_unit():
    with pytest.raises(NormalizationError, match="not 'WEF'"):
        workbook_key(CATALOG.dataset("WB_AVELEC"))
    with pytest.raises(NormalizationError, match="organization_series_code"):
        workbook_key(with_source(organization_series_code=None))
    with pytest.raises(NormalizationError, match="no canonical unit"):
        normalize_wef_dataset(dataclasses.replace(DATASET, unit=None), synthetic())
    with pytest.raises(NormalizationError, match="is not the dataset's"):
        normalize_wef_dataset(DATASET, dataclasses.replace(synthetic(), key="other"))


def test_a_file_that_is_not_a_workbook_is_a_source_error():
    with pytest.raises(SourceResponseError, match="not a readable Excel file"):
        normalize_wef_dataset(DATASET, dataclasses.replace(synthetic(), content=b"<html>"))


def test_the_legacy_unit_rule():
    assert legacy_unit("Quality of electricity supply, 1-7 (best)") == "1-7 (best)"
    assert legacy_unit("A, b, c") == "b" and legacy_unit("No comma") == ""
