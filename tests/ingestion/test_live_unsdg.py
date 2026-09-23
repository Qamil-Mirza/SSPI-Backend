"""Opt-in smoke test against the live UN SDG API.

Skipped unless SSPI_LIVE_SOURCE_TESTS=1. Never required by the ordinary
suite. Touches no database.
"""

import os

import pytest

from sspi.ingestion.unsdg import UNSDGClient, normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

pytestmark = pytest.mark.live


live_only = pytest.mark.skipif(os.environ.get("SSPI_LIVE_SOURCE_TESTS") != "1", reason="set SSPI_LIVE_SOURCE_TESTS=1 to call the live UN SDG API")


def check(dataset, rows, result):
    assert len(rows) >= 150
    assert {o.dataset_code for o in result.observations} == {dataset.code}
    assert "MYS" in {o.country_code for o in result.observations}
    identities = [(o.country_code, o.year) for o in result.observations]
    assert len(identities) == len(set(identities))
    assert all(o.unit == "PERCENT" for o in result.observations)
    assert all(name for _, name in result.skipped_areas)


@live_only
def test_live_unsdg_marine_fetch_and_normalize():
    dataset = MetadataCatalog.load().dataset("UNSDG_MARINE")
    with UNSDGClient(timeout=60.0) as client:
        rows = client.fetch_indicator(dataset.source.query_code)
    check(dataset, rows, normalize_unsdg_dataset(dataset, rows))


@live_only
def test_live_unsdg_terrestrial_and_freshwater_share_one_fetch():
    catalog = MetadataCatalog.load()
    terrst, frshwt = catalog.dataset("UNSDG_TERRST"), catalog.dataset("UNSDG_FRSHWT")
    assert terrst.source.query_code == frshwt.source.query_code == "15.1.2"
    with UNSDGClient(timeout=60.0) as client:
        rows = client.fetch_indicator("15.1.2")
    t, f = normalize_unsdg_dataset(terrst, rows), normalize_unsdg_dataset(frshwt, rows)
    check(terrst, rows, t)
    check(frshwt, rows, f)
    assert len(t.observations) != len(f.observations)
