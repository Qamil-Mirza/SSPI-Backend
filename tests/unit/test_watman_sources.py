"""WATMAN source work: declared source dimensions, the UNSDG_WUSEFF addition,
and the derived UNSDG_CWUEFF dataset. The indicator itself is not registered
yet (its imputation needs the strategy interface). No database, no network."""

import dataclasses
import json
from pathlib import Path

import pytest

from sspi.errors import DuplicateObservationError, MetadataError, NotIngestibleError
from sspi.ingestion.derived import DERIVATIONS, baseline_change_2000_2005
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog
from sspi.metadata.loader import load_catalog_data
from sspi.scoring import Observation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
ROWS = {q: json.loads((FIXTURES / f"{q.replace('.', '_')}_sample.json").read_text())["data"] for q in ("6.4.1", "6.4.2")}


class FakeClient:
    def __init__(self):
        self.fetched = []

    def fetch_indicator(self, code):
        self.fetched.append(code)
        return ROWS[code]


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


def test_canonical_source_metadata(metadata):
    wtstrs, wuseff, cwueff = (metadata.dataset(c) for c in ("UNSDG_WTSTRS", "UNSDG_WUSEFF", "UNSDG_CWUEFF"))
    assert (wtstrs.source.query_code, wtstrs.source.organization_series_code, wtstrs.source.dimensions, wtstrs.unit) == ("6.4.2", "ER_H2O_STRESS", {"activity": "TOTAL"}, "PERCENT")
    assert (wuseff.source.query_code, wuseff.source.organization_series_code, wuseff.source.dimensions, wuseff.unit) == ("6.4.1", "ER_H2O_WUEYST", {"activity": "TOTAL"}, "USD/m3")
    assert (cwueff.source.query_code, cwueff.source.organization_series_code, cwueff.source.dimensions, cwueff.unit) == ("6.4.1", "ER_H2O_WUEYST", {"activity": "TOTAL"}, "Percent")
    assert "UNSDG_WUSEFF" in cwueff.source.note
    assert metadata.indicator("WATMAN").dataset_codes == ("UNSDG_CWUEFF", "UNSDG_WTSTRS")  # WUSEFF is an imputation input, not a dependency


def test_wuseff_addition_is_recorded_in_provenance():
    import yaml

    provenance = yaml.safe_load((Path(__file__).parents[2] / "src/sspi/metadata/data/PROVENANCE.yaml").read_text())
    assert [a["file"] for a in provenance["additions"]] == ["datasets/UNSDG_WUSEFF.yaml"]
    fields = {(e["file"], e["field"]) for e in provenance["edits"]}
    assert {("datasets/UNSDG_WTSTRS.yaml", "source.dimensions"), ("datasets/UNSDG_CWUEFF.yaml", "source.organization_series_code")} <= fields


def test_dimension_filter_is_applied_before_duplicate_detection(metadata):
    dataset = metadata.dataset("UNSDG_WTSTRS")
    result = normalize_unsdg_dataset(dataset, ROWS["6.4.2"])
    assert len(result.observations) == 168 and all(o.provenance["source_dimensions"] == {"activity": "TOTAL"} for o in result.observations)
    undeclared = dataclasses.replace(dataset, source=dataclasses.replace(dataset.source, dimensions=None))
    with pytest.raises(DuplicateObservationError, match="activity"):
        normalize_unsdg_dataset(undeclared, ROWS["6.4.2"])


def test_wtstrs_values(metadata):
    values = {(o.country_code, o.year): o.value for o in normalize_unsdg_dataset(metadata.dataset("UNSDG_WTSTRS"), ROWS["6.4.2"]).observations}
    assert values[("MYS", 2022)] == 3.44 and values[("AUT", 2005)] == 9.79
    assert sorted({y for _, y in values}) == list(range(2000, 2024))


def test_cwueff_is_derived_from_wuseff(metadata):
    assert DERIVATIONS["UNSDG_CWUEFF"].base == "UNSDG_WUSEFF" and DERIVATIONS["UNSDG_CWUEFF"].transform is baseline_change_2000_2005
    client = FakeClient()
    results, fetches = fetch_and_normalize(resolve_datasets(["UNSDG_WUSEFF", "UNSDG_CWUEFF"], metadata), client, metadata=metadata)
    assert client.fetched == ["6.4.1"] == list(fetches)  # one fetch for the base and the derived dataset
    wuseff, cwueff = ({d.code: r for d, r in results}[c] for c in ("UNSDG_WUSEFF", "UNSDG_CWUEFF"))
    assert len(wuseff.observations) == 150 and len(cwueff.observations) == 108
    assert {o.dataset_code for o in cwueff.observations} == {"UNSDG_CWUEFF"} and {o.unit for o in cwueff.observations} == {"Percent"}
    assert sorted({o.year for o in cwueff.observations}) == list(range(2006, 2024))  # nothing before 2006
    mys = {o.year: o for o in cwueff.observations if o.country_code == "MYS"}
    base = {o.year: o.value for o in wuseff.observations if o.country_code == "MYS"}
    baseline = sum(base[y] for y in range(2000, 2006)) / 6
    assert mys[2022].value == ((base[2022] - baseline) / baseline) * 100
    assert mys[2022].provenance["derived_from"] == "UNSDG_WUSEFF" and mys[2022].provenance["baseline_value"] == baseline
    assert mys[2022].provenance["baseline_observation_count"] == 6 and mys[2022].provenance["source_value"] == base[2022]
    assert (cwueff.skipped_areas, cwueff.missing_values) == (wuseff.skipped_areas, wuseff.missing_values)


def test_country_without_a_baseline_produces_nothing():
    dataset = MetadataCatalog.load().dataset("UNSDG_CWUEFF")
    base = [Observation("UNSDG_WUSEFF", "XXX", y, float(y), "USD/m3") for y in range(2010, 2015)]
    base += [Observation("UNSDG_WUSEFF", "YYY", y, 10.0 if y < 2006 else 12.5, "USD/m3") for y in range(2003, 2008)]
    derived = baseline_change_2000_2005(dataset, base)
    assert [(o.country_code, o.year, o.value) for o in derived] == [("YYY", 2006, 25.0), ("YYY", 2007, 25.0)]


def test_zero_baseline_gives_zero_change():
    dataset = MetadataCatalog.load().dataset("UNSDG_CWUEFF")
    base = [Observation("UNSDG_WUSEFF", "ZZZ", y, 0.0 if y < 2006 else 3.0, "USD/m3") for y in range(2000, 2008)]
    assert [o.value for o in baseline_change_2000_2005(dataset, base)] == [0.0, 0.0]


def test_derived_dataset_whose_base_source_disagrees_is_refused(metadata, monkeypatch):
    from sspi.ingestion import runner

    cwueff = metadata.dataset("UNSDG_CWUEFF")
    drifted = dataclasses.replace(cwueff, source=dataclasses.replace(cwueff.source, query_code="6.4.9"))
    with pytest.raises(NotIngestibleError, match="canonical sources disagree"):
        fetch_and_normalize((drifted,), FakeClient(), metadata=metadata)


def test_loader_validates_dimensions(tmp_path):
    root = tmp_path / "data"
    (root / "indicators").mkdir(parents=True)
    (root / "datasets").mkdir()
    (root / "indicators" / "X.yaml").write_text("code: X\nname: X\npillar_code: P\ncategory_code: C\ndescription: d\ndataset_codes: [DS]\n")
    good = "code: DS\nstatus: documented\nname: n\ndataset_type: t\nunit: u\nsource:\n  organization_code: UNSDG\n  query_code: q\n  organization_series_code: s\n  dimensions:\n    activity: TOTAL\n"
    (root / "datasets" / "DS.yaml").write_text(good)
    assert load_catalog_data(root).datasets["DS"].source.dimensions == {"activity": "TOTAL"}
    (root / "datasets" / "DS.yaml").write_text(good.replace("    activity: TOTAL\n", "    activity: 3\n"))
    with pytest.raises(MetadataError, match="source.dimensions"):
        load_catalog_data(root)
    (root / "datasets" / "DS.yaml").write_text(good.replace("  dimensions:\n    activity: TOTAL\n", "  dimensions: {}\n"))
    with pytest.raises(MetadataError, match="source.dimensions"):
        load_catalog_data(root)
