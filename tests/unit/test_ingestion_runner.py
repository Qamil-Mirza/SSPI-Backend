"""Ingestion orchestration without a database or network: request forms,
validation order, source dispatch, shared fetches, client ownership."""

import json
from pathlib import Path

import pytest

from sspi.errors import IngestionRequestError, NotIngestibleError, UnknownCodeError
from sspi.ingestion import runner
from sspi.ingestion.runner import SUPPORTED_DATASETS, DatasetIngestion, IngestionRun, fetch_and_normalize, ingest_datasets, normalize_request, resolve_datasets
from sspi.metadata import DatasetMetadata, MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}


class FakeClient:
    def __init__(self, payloads=PAYLOADS):
        self.payloads, self.fetched, self.closed = payloads, [], False

    def fetch_indicator(self, code):
        self.fetched.append(code)
        return self.payloads[code]

    def close(self):
        self.closed = True


class ForbiddenClient(FakeClient):
    def fetch_indicator(self, code):
        raise AssertionError(f"network access attempted for {code}")


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


# --- request forms -------------------------------------------------------------------


@pytest.mark.parametrize("request_, expected", [("UNSDG_MARINE", ("UNSDG_MARINE",)), (["UNSDG_TERRST", "UNSDG_MARINE"], ("UNSDG_TERRST", "UNSDG_MARINE")), (("UNSDG_FRSHWT",), ("UNSDG_FRSHWT",))])
def test_accepted_forms_preserve_order(request_, expected):
    assert normalize_request(request_) == expected


@pytest.mark.parametrize("bad", [{"UNSDG_MARINE"}, iter(["UNSDG_MARINE"]), 42, None, ["UNSDG_MARINE", 3], [""], "", [], ()])
def test_other_forms_empty_and_non_string_entries_are_rejected(bad):
    with pytest.raises(IngestionRequestError):
        normalize_request(bad)


def test_duplicate_codes_are_rejected_not_deduplicated():
    with pytest.raises(IngestionRequestError, match="UNSDG_MARINE"):
        normalize_request(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_MARINE"])


# --- validation and dispatch ----------------------------------------------------------


def test_supported_datasets_are_an_explicit_list():
    assert SUPPORTED_DATASETS[:4] == ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT", "UNSDG_REDLST")
    assert set(SUPPORTED_DATASETS[4:]) == {"UNSDG_STKHLM", "UNSDG_MINMAT", "UNSDG_MONTRL", "UNSDG_BASELA", "UNSDG_ROTDAM", "UNSDG_WTSTRS", "UNSDG_WUSEFF", "UNSDG_CWUEFF"}
    assert len(set(SUPPORTED_DATASETS)) == len(SUPPORTED_DATASETS)


def test_resolve_returns_dataset_metadata_in_request_order(metadata):
    datasets = resolve_datasets(("UNSDG_FRSHWT", "UNSDG_MARINE"), metadata)
    assert [d.code for d in datasets] == ["UNSDG_FRSHWT", "UNSDG_MARINE"] and all(isinstance(d, DatasetMetadata) for d in datasets)


def test_unknown_code_is_an_unknown_code_error(metadata):
    with pytest.raises(UnknownCodeError):
        resolve_datasets(["UNSDG_MARINE", "NOT_REAL"], metadata)


def test_known_but_not_ingestible_dataset_gets_a_distinct_error(metadata):
    with pytest.raises(NotIngestibleError, match="no ingestion path") as info:
        resolve_datasets("UNSDG_AIRPOL", metadata)
    assert "UNSDG_AIRPOL" in str(info.value) and "UNSDG_MARINE" in str(info.value)
    other = next(d for d in metadata.datasets() if d.source.organization_code != "UNSDG")
    with pytest.raises(NotIngestibleError, match=other.source.organization_code):
        resolve_datasets(other.code, metadata)
    unresolved = metadata.unresolved_datasets()[0]
    with pytest.raises(NotIngestibleError):
        resolve_datasets(unresolved.code, metadata)


def test_validation_happens_before_any_network_or_database_use(metadata):
    client = ForbiddenClient()
    with pytest.raises(UnknownCodeError):
        ingest_datasets("NOT_REAL", database=None, metadata=metadata, client=client)
    with pytest.raises(NotIngestibleError):
        ingest_datasets(["UNSDG_MARINE", "UNSDG_AIRPOL"], database=None, metadata=metadata, client=client)
    with pytest.raises(IngestionRequestError):
        ingest_datasets([], database=None, metadata=metadata, client=client)


# --- shared fetch ------------------------------------------------------------------------


def test_datasets_sharing_a_query_are_fetched_once(metadata):
    client = FakeClient()
    normalized, fetches = fetch_and_normalize(resolve_datasets(["UNSDG_TERRST", "UNSDG_FRSHWT", "UNSDG_MARINE"], metadata), client, metadata=metadata)
    assert client.fetched == ["15.1.2", "14.5.1"] == list(fetches)
    assert [(d.code, len(r.observations)) for d, r in normalized] == [("UNSDG_TERRST", 104), ("UNSDG_FRSHWT", 104), ("UNSDG_MARINE", 104)]
    assert {o.dataset_code for d, r in normalized for o in r.observations if d.code == "UNSDG_FRSHWT"} == {"UNSDG_FRSHWT"}


def test_fetch_order_follows_first_appearance(metadata):
    client = FakeClient()
    fetch_and_normalize(resolve_datasets(["UNSDG_MARINE", "UNSDG_FRSHWT"], metadata), client, metadata=metadata)
    assert client.fetched == ["14.5.1", "15.1.2"]


# --- client ownership ----------------------------------------------------------------------


def test_internally_created_client_is_closed_even_on_failure(metadata, monkeypatch):
    created = []

    class Failing(FakeClient):
        def __init__(self):
            super().__init__({})
            created.append(self)

    monkeypatch.setattr(runner, "UNSDGClient", Failing)
    with pytest.raises(KeyError):  # payload lookup fails: stands in for any source error
        ingest_datasets("UNSDG_MARINE", database=None, metadata=metadata)
    assert len(created) == 1 and created[0].closed is True


def test_injected_client_is_never_closed(metadata):
    client = FakeClient({})
    with pytest.raises(KeyError):
        ingest_datasets("UNSDG_MARINE", database=None, metadata=metadata, client=client)
    assert client.closed is False


# --- result shape ----------------------------------------------------------------------------


def test_result_totals_and_counts_derive_from_per_dataset_entries():
    per = (DatasetIngestion("UNSDG_TERRST", "15.1.2", 104, (("1", "World"),), 3), DatasetIngestion("UNSDG_MARINE", "14.5.1", 100, (), 0))
    run = IngestionRun(("UNSDG_TERRST", "UNSDG_MARINE"), per, ("15.1.2", "14.5.1"))
    assert run.observations_written == 204 and run.counts == {"UNSDG_TERRST": 104, "UNSDG_MARINE": 100}
    assert run.per_dataset[0].skipped_areas == (("1", "World"),) and run.per_dataset[0].missing_values == 3
