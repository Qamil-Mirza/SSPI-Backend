"""MetadataCatalog behaviour on the bundled canonical metadata."""

import pytest

import sspi.metadata.loader as loader
from sspi.errors import UnknownCodeError
from sspi.metadata import DatasetMetadata, IndicatorMetadata, MetadataCatalog, UnresolvedDataset


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def test_biodiv_resolves_to_its_three_unsdg_datasets(catalog):
    biodiv = catalog.indicator("BIODIV")
    assert isinstance(biodiv, IndicatorMetadata)
    assert biodiv.code == "BIODIV"
    assert biodiv.name == "Biodiversity Protection"
    assert biodiv.pillar_code == "SUS"
    assert biodiv.category_code == "ECO"
    assert biodiv.dataset_codes == ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT")
    assert biodiv.lower_goalpost is None and biodiv.upper_goalpost is None
    assert biodiv.policy == "Protection of Biodiversity"
    assert "goalpost(UNSDG_MARINE, 0, 100)" in biodiv.score_function


def test_biodiv_dependencies_are_dataset_records_in_declared_order(catalog):
    deps = catalog.dataset_dependencies("BIODIV")
    assert [d.code for d in deps] == ["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"]
    assert all(isinstance(d, DatasetMetadata) for d in deps)


def test_redlst_resolves_to_unsdg_redlst(catalog):
    assert catalog.indicator("REDLST").dataset_codes == ("UNSDG_REDLST",)
    assert [d.code for d in catalog.dataset_dependencies("REDLST")] == ["UNSDG_REDLST"]


def test_unsdg_marine_loads_correctly(catalog):
    marine = catalog.dataset("UNSDG_MARINE")
    assert isinstance(marine, DatasetMetadata)
    assert marine.code == "UNSDG_MARINE"
    assert marine.name == "Marine Areas Protected"
    assert marine.organization_code == "UNSDG"
    assert marine.source.organization_code == "UNSDG"
    assert marine.source.query_code == "14.5.1"
    assert marine.source.organization_series_code == "ER_MRN_MPA"  # corrected at import; see PROVENANCE.yaml edits
    assert marine.unit == "PERCENT"
    assert marine.dataset_type == "Intermediate"
    assert marine.description == "Percentage of important sites covered by protected areas, marine"


def test_goalposts_are_floats_and_inverted_bounds_survive(catalog):
    mswgen = catalog.indicator("MSWGEN")
    assert (mswgen.lower_goalpost, mswgen.upper_goalpost) == (100.0, 0.0)
    assert isinstance(mswgen.lower_goalpost, float)


def test_counts(catalog):
    assert len(catalog.indicators()) == 57
    assert len(catalog.datasets()) == 87
    assert len(catalog.unresolved_datasets()) == 2


def test_listings_are_sorted_by_code(catalog):
    codes = [i.code for i in catalog.indicators()]
    assert codes == sorted(codes)
    dcodes = [d.code for d in catalog.datasets()]
    assert dcodes == sorted(dcodes)


def test_every_dependency_resolves_to_a_typed_record(catalog):
    for indicator in catalog.indicators():
        for dep in catalog.dataset_dependencies(indicator.code):
            assert isinstance(dep, (DatasetMetadata, UnresolvedDataset))


def test_unresolved_dependency_is_explicit_not_fabricated(catalog):
    (dep,) = catalog.dataset_dependencies("FSTABL")
    assert isinstance(dep, UnresolvedDataset)
    assert dep.code == "IMF_FSTABL"
    assert "no dataset definition" in dep.note
    assert {u.code for u in catalog.unresolved_datasets()} == {"IMF_FSTABL", "WB_RAILNT"}
    assert "IMF_FSTABL" not in {d.code for d in catalog.datasets()}


def test_reverse_lookup(catalog):
    assert [i.code for i in catalog.indicators_using("WB_POPULN")] == ["BEEFMK", "FORAID", "GTRANS"]
    assert [i.code for i in catalog.indicators_using("UNSDG_MARINE")] == ["BIODIV"]
    assert [i.code for i in catalog.indicators_using("WB_RAILNT")] == ["TRNETW"]


def test_unknown_codes_raise_unknown_code_error(catalog):
    with pytest.raises(UnknownCodeError):
        catalog.indicator("NOPE")
    with pytest.raises(UnknownCodeError):
        catalog.dataset("NOPE")
    with pytest.raises(UnknownCodeError):
        catalog.dataset_dependencies("NOPE")
    with pytest.raises(UnknownCodeError):
        catalog.indicators_using("NOPE")
    assert issubclass(UnknownCodeError, KeyError)


def test_records_are_immutable(catalog):
    biodiv = catalog.indicator("BIODIV")
    with pytest.raises(AttributeError):
        biodiv.name = "x"  # type: ignore[misc]


def test_loading_twice_is_deterministic():
    assert MetadataCatalog.load() == MetadataCatalog.load()


def test_queries_do_not_reparse_files(monkeypatch):
    catalog = MetadataCatalog.load()

    def boom(path):
        raise AssertionError(f"file read during query: {path}")

    monkeypatch.setattr(loader, "read_yaml", boom)
    catalog.indicator("BIODIV")
    catalog.dataset("UNSDG_MARINE")
    catalog.indicators()
    catalog.datasets()
    catalog.unresolved_datasets()
    catalog.dataset_dependencies("BIODIV")
    catalog.indicators_using("UNSDG_MARINE")


def test_load_reads_each_file_exactly_once(monkeypatch):
    reads = []
    real = loader.read_yaml

    def counting(path):
        reads.append(path)
        return real(path)

    monkeypatch.setattr(loader, "read_yaml", counting)
    MetadataCatalog.load()
    assert len(reads) == 57 + 89
    assert len(set(reads)) == len(reads)
