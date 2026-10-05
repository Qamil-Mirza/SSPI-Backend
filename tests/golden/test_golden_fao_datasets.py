"""Observation parity for the FAO Land Use datasets: the new bulk-file adapter
plus the 1990s-average derivations must reproduce the legacy cleaners
(``clean_unfao_frstlv`` / ``_frstav`` / ``_crbnlv`` / ``_crbnav``) exactly, from
the same committed bulk-file sample.

``generate_fao_land_cases.py`` presented the bulk rows to the legacy cleaner
the way the FAOSTAT API did (ISO3 where the M49 code is a country, the FAO
area code otherwise); everything after that is the legacy code's own output.
"""

import pytest

from sspi.ingestion.derived import DERIVATIONS
from sspi.ingestion.fao import read_bulk_csv, source_filters
from sspi.ingestion.runner import fetch_and_normalize
from sspi.metadata import MetadataCatalog
from tests.golden.parity import OBSERVATION_CASES, OBSERVATION_IDENTITY, assert_parity, load_cases, observation_record, source_fixtures, summary

CASES = {code: load_cases(filename) for code, filename in OBSERVATION_CASES.items() if code.startswith("UNFAO_")}


class _BulkClient:
    def __init__(self, rows):
        self.rows = rows

    def fetch_domain(self, domain):
        return self.rows


@pytest.fixture(scope="module", params=list(CASES), ids=list(CASES))
def parity(request):
    case = CASES[request.param]
    catalog = MetadataCatalog.load()
    dataset = catalog.dataset(request.param)
    (fixture_path,) = source_fixtures(case)
    rows = read_bulk_csv(fixture_path.read_text(encoding="utf-8"), "RL")
    ((_, result),), _ = fetch_and_normalize((dataset,), _BulkClient(rows), metadata=catalog)  # derived datasets go through their base, as ingestion does
    return case, dataset, rows, result


def test_golden_file_describes_this_dataset(parity):
    case, dataset, _, _ = parity
    filters = source_filters(dataset)
    assert case["dataset_code"] == dataset.code
    assert case["source_filters"] == {"domain": filters.domain, "element_code": filters.element_code, "item_code": filters.item_code}


def test_observations_match_legacy_cleaner(parity):
    case, dataset, _, result = parity
    assert {o.dataset_code for o in result.observations} == {dataset.code}
    new = [observation_record(o) for o in result.observations]
    assert_parity(f"{dataset.code} observations", new, case["observations"], OBSERVATION_IDENTITY)
    assert summary(new) == summary(case["observations"])  # count, country coverage, year range


def test_skipped_areas_are_exactly_the_non_iso3_areas_legacy_dropped(parity):
    case, _, _, result = parity
    assert sorted(list(a) for a in result.skipped_areas) == sorted(case["skipped_areas"])


def test_missing_source_values_are_exactly_the_cells_legacy_omitted(parity):
    """Every selected row of a mapped area is either a legacy observation or an
    empty source value; nothing else is dropped and nothing is invented."""
    case, dataset, rows, result = parity
    filters = source_filters(dataset)
    skipped = {code for code, _ in result.skipped_areas}
    selected = [r for r in rows if r["Element Code"] == filters.element_code and r["Item Code"] == filters.item_code and r["Area Code"] not in skipped]
    empty = sum(1 for r in selected if r["Value"] == "")
    assert result.missing_values == empty == case["empty_source_values"]
    if dataset.code not in DERIVATIONS:
        assert len(case["observations"]) == len(selected) - empty == len(result.observations)


def test_derived_units_are_the_legacy_labels():
    assert {o["unit"] for o in CASES["UNFAO_FRSTAV"]["observations"]} == {"hectares (1990s Average)"}
    assert {o["unit"] for o in CASES["UNFAO_CRBNAV"]["observations"]} == {"millions of kilograms (1990s Average)"}
    assert {o["unit"] for o in CASES["UNFAO_CRBNLV"]["observations"]} == {"million t"}  # the label above mislabels this unit (PROVENANCE.yaml)


def test_derived_year_coverage_asymmetry_is_legacy(parity):
    """FRSTAV stops at 2022 whatever the source covers; CRBNAV follows the source (DEFRST-2)."""
    case, dataset, _, result = parity
    years = {o.year for o in result.observations}
    if dataset.code == "UNFAO_FRSTAV":
        assert (min(years), max(years)) == (1990, 2022)
    if dataset.code == "UNFAO_CRBNAV":
        assert max(years) == max(o["year"] for o in CASES["UNFAO_CRBNLV"]["observations"]) > 2022
