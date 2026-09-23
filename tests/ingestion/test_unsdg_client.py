"""UNSDGClient: request construction, pagination, and failure modes, with an
injected httpx transport. No network."""

import json

import httpx
import pytest

from sspi.errors import IngestionError, SourceRequestError, SourceResponseError
from sspi.ingestion.unsdg import PIVOT_DATA_URL, UNSDGClient


def row(series="ER_MRN_MPA", geo="458", name="Malaysia", years=None):
    entries = years if years is not None else [{"year": "[2020]", "value": "60.0", "Nature": "C", "Observation Status": "A", "Units": "PERCENT", "UnitMultiplier": ""}]
    return {"goal": "14", "target": "14.5", "indicator": "14.5.1", "series": series, "seriesDescription": "desc", "seriesCount": "1",
            "geoAreaCode": geo, "geoAreaName": name, "units": "PERCENT", "sex": None, "age": None, "years": json.dumps(entries)}


def payload(rows, page, page_size, total):
    total_pages = -(-total // page_size) if total else 0
    return {"size": page_size, "totalElements": total, "totalPages": total_pages, "pageNumber": page, "attributes": [], "dimensions": [], "data": rows}


class Server:
    """Serves `rows` in pages, recording every request."""

    def __init__(self, rows, page_size=500):
        self.rows, self.page_size, self.requests = rows, page_size, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        page = int(request.url.params.get("page", "1"))
        size = int(request.url.params["pageSize"])
        chunk = self.rows[(page - 1) * size: page * size]
        return httpx.Response(200, json=payload(chunk, page, size, len(self.rows)))


def client_for(handler, **kwargs) -> UNSDGClient:
    return UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, **kwargs)


def test_request_construction():
    server = Server([row()])
    rows = client_for(server).fetch_indicator("14.5.1")
    assert len(rows) == 1
    (request,) = server.requests
    assert request.method == "GET"
    assert str(request.url).startswith(PIVOT_DATA_URL)
    assert PIVOT_DATA_URL == "https://unstats.un.org/SDGAPI/v1/sdg/Indicator/PivotData"
    assert dict(request.url.params) == {"indicator": "14.5.1", "pageSize": "500", "page": "1"}


def test_pagination_assembles_all_pages_in_order():
    rows = [row(geo=str(100 + i), name=f"Area {i}") for i in range(7)]
    server = Server(rows, page_size=3)
    fetched = client_for(server, page_size=3).fetch_indicator("14.5.1")
    assert [r["geoAreaCode"] for r in fetched] == [r["geoAreaCode"] for r in rows]
    assert [int(r.url.params["page"]) for r in server.requests] == [1, 2, 3]
    assert {r.url.params["pageSize"] for r in server.requests} == {"3"}


def test_pause_between_pages_uses_injected_sleeper():
    slept = []
    server = Server([row(geo=str(i)) for i in range(4)], page_size=2)
    UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(server)), page_size=2, pause_between_pages=0.25, sleep=slept.append).fetch_indicator("14.5.1")
    assert slept == [0.25]  # once, between page 1 and page 2


def test_http_error_status_is_a_source_request_error():
    def handler(request):
        return httpx.Response(503, text="unavailable")

    with pytest.raises(SourceRequestError, match="503"):
        client_for(handler).fetch_indicator("14.5.1")


def test_transport_failure_is_a_source_request_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(SourceRequestError, match="14.5.1"):
        client_for(handler).fetch_indicator("14.5.1")


def test_invalid_json_is_a_source_response_error():
    def handler(request):
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(SourceResponseError, match="JSON"):
        client_for(handler).fetch_indicator("14.5.1")


@pytest.mark.parametrize(
    "body",
    [
        ["a", "list"],
        {"size": 500, "totalElements": 1, "pageNumber": 1, "data": []},  # missing totalPages
        {"size": 500, "totalElements": 1, "totalPages": 1, "pageNumber": 1, "data": "nope"},
        {"size": 500, "totalElements": "1", "totalPages": 1, "pageNumber": 1, "data": []},
    ],
)
def test_malformed_body_is_a_source_response_error(body):
    with pytest.raises(SourceResponseError):
        client_for(lambda request: httpx.Response(200, json=body)).fetch_indicator("14.5.1")


def test_empty_or_unknown_indicator_is_a_source_response_error():
    # The live API answers 200 with totalElements 0 for an unknown indicator.
    with pytest.raises(SourceResponseError, match="no data"):
        client_for(lambda request: httpx.Response(200, json=payload([], 1, 500, 0))).fetch_indicator("99.99.99")


def test_page_number_mismatch_is_a_source_response_error():
    def handler(request):
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=payload([row()], 1 if page == 1 else 7, 1, 2))

    with pytest.raises(SourceResponseError, match="page"):
        client_for(handler, page_size=1).fetch_indicator("14.5.1")


def test_row_count_mismatch_is_a_source_response_error():
    body = payload([row()], 1, 500, 5)  # claims 5, delivers 1 on a single page
    with pytest.raises(SourceResponseError, match="5"):
        client_for(lambda request: httpx.Response(200, json=body)).fetch_indicator("14.5.1")


def test_errors_share_one_hierarchy_and_hide_httpx():
    assert issubclass(SourceRequestError, IngestionError)
    assert issubclass(SourceResponseError, IngestionError)
    assert not issubclass(SourceRequestError, httpx.HTTPError)


def test_client_owns_its_http_client_when_not_injected():
    client = UNSDGClient(timeout=5.0)
    assert isinstance(client.http, httpx.Client)
    assert client.http.timeout.read == 5.0
    client.close()
