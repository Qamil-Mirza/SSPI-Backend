"""Declared source units and value multipliers (``source.published_unit``,
``source.value_multiplier``): loader validation, the shared helpers in
``sspi.ingestion.units``, and how the IEA and FAOSTAT normalizers apply them.
A dataset that declares neither is normalized exactly as before. No network,
no database."""

import pytest
import yaml

from sspi.errors import MetadataError, NormalizationError
from sspi.ingestion.fao import normalize_fao_dataset
from sspi.ingestion.iea import normalize_iea_dataset
from sspi.ingestion.units import conversion_provenance, expected_source_unit, stored_value, unit_expectation
from sspi.metadata import DatasetMetadata, MetadataCatalog, SourceMetadata


def iea_dataset(published_unit=None, multiplier=None, unit="Tonnes C02 per inhabitant"):
    source = SourceMetadata("IEA", "CO2BySector", dimensions={"seriesLabel": "Transport Sector"}, published_unit=published_unit, value_multiplier=multiplier)
    return DatasetMetadata("IEA_TEST", "t", "Intermediate", source, unit=unit)


def co2_row(country="MYS", year="2022", value=61.342, units="MtCO2", series="Transport Sector"):
    return {"year": year, "short": "MALAYSIA", "flow": "TOTTRANS", "value": value, "flowLabel": series, "units": units, "product": "TOTAL", "productLabel": "Total", "seriesLabel": series, "country": country}


def fao_dataset(published_unit=None, unit="kg/capita/year"):
    return DatasetMetadata("UNFAO_TEST", "t", "Intermediate", SourceMetadata("UNFAO", "Domain=FBS;Element=645;Item=2731", published_unit=published_unit), unit=unit)


def fao_row(value="8.75", unit="kg/cap", m49="'458", area="Malaysia"):
    return {"Area Code": "131", "Area Code (M49)": m49, "Area": area, "Item Code": "2731", "Item Code (FBS)": "'S2731", "Item": "Bovine Meat", "Element Code": "645", "Element": "Food supply quantity (kg/capita/yr)", "Year Code": "2023", "Year": "2023", "Unit": unit, "Value": value, "Flag": "E", "Note": ""}


# --- the helpers --------------------------------------------------------------------------------


def test_helpers_without_a_declaration_change_nothing():
    plain = iea_dataset(unit="TJ")
    assert expected_source_unit(plain) == "TJ" and stored_value(plain, 12.5) == 12.5 and conversion_provenance(plain, "TJ", 12.5) == {}
    assert unit_expectation(plain) == "canonical unit 'TJ'"


def test_helpers_with_a_declaration():
    declared = iea_dataset("MtCO2", 10**9)
    assert expected_source_unit(declared) == "MtCO2" and stored_value(declared, 1.5) == 1.5 * 10**9 == 1500000000.0
    assert conversion_provenance(declared, "MtCO2", 1.5) == {"source_unit": "MtCO2", "source_value": 1.5, "value_multiplier": 10**9}
    assert "published unit 'MtCO2'" in unit_expectation(declared)
    relabel_only = fao_dataset("kg/cap")
    assert stored_value(relabel_only, 8.75) == 8.75 and conversion_provenance(relabel_only, "kg/cap", 8.75) == {"source_unit": "kg/cap"}


# --- IEA ----------------------------------------------------------------------------------------


def test_iea_multiplies_and_writes_the_canonical_label():
    result = normalize_iea_dataset(iea_dataset("MtCO2", 10**9), [co2_row(), co2_row(series="Industry Sector", value=5.0)])
    (o,) = result.observations
    assert (o.value, o.unit) == (61.342 * 10**9, "Tonnes C02 per inhabitant") and o.value == 61342000000.0
    assert (o.provenance["source_unit"], o.provenance["source_value"], o.provenance["value_multiplier"]) == ("MtCO2", 61.342, 10**9)


def test_iea_integer_source_values_multiply_to_the_same_number_as_legacy():
    (o,) = normalize_iea_dataset(iea_dataset("MtCO2", 10**9), [co2_row(value=5)]).observations
    assert o.value == 5 * 10**9 and isinstance(o.value, float)


def test_iea_checks_the_published_unit_not_the_canonical_label():
    with pytest.raises(NormalizationError, match="published unit 'MtCO2' declared for canonical unit"):
        normalize_iea_dataset(iea_dataset("MtCO2", 10**9), [co2_row(units="ktCO2")])
    with pytest.raises(NormalizationError, match="disagrees with canonical unit"):
        normalize_iea_dataset(iea_dataset(), [co2_row()])  # no declaration: the source unit must be the canonical label


def test_iea_zero_and_null_stay_missing_before_any_multiplication():
    result = normalize_iea_dataset(iea_dataset("MtCO2", 10**9), [co2_row(value=0), co2_row(year="2021", value=None), co2_row(year="2020")])
    assert [o.year for o in result.observations] == [2020] and result.missing_values == 2


# --- FAOSTAT ------------------------------------------------------------------------------------


def test_fao_relabels_without_changing_the_value():
    (o,) = normalize_fao_dataset(fao_dataset("kg/cap"), [fao_row()]).observations
    assert (o.country_code, o.year, o.value, o.unit) == ("MYS", 2023, 8.75, "kg/capita/year") and o.provenance["source_unit"] == "kg/cap"
    assert "value_multiplier" not in o.provenance


def test_fao_checks_the_published_unit():
    with pytest.raises(NormalizationError, match="published unit 'kg/cap'"):
        normalize_fao_dataset(fao_dataset("kg/cap"), [fao_row(unit="g/cap/d")])
    with pytest.raises(NormalizationError, match="disagrees with canonical unit 'kg/capita/year'"):
        normalize_fao_dataset(fao_dataset(), [fao_row()])


# --- canonical metadata and the loader -----------------------------------------------------------


def test_canonical_declarations():
    catalog = MetadataCatalog.load()
    declared = {d.code: (d.source.published_unit, d.source.value_multiplier) for d in catalog.datasets() if d.source.published_unit or d.source.value_multiplier}
    assert declared == {"IEA_TCO2EM": ("MtCO2", 1000000000), "UNFAO_BFCONS": ("kg/cap", None)}
    assert isinstance(catalog.dataset("IEA_TCO2EM").source.value_multiplier, int)  # kept as written, so the product is the legacy one


def write_tree(root, source):
    (root / "indicators").mkdir()
    (root / "datasets").mkdir()
    indicator = {"code": "IND001", "name": "I", "pillar_code": "SUS", "category_code": "GHG", "description": "d", "dataset_codes": ["DS_A"], "lower_goalpost": 0, "upper_goalpost": 1}
    dataset = {"code": "DS_A", "status": "documented", "name": "D", "dataset_type": "Intermediate", "unit": "kg", "source": {"organization_code": "IEA", "query_code": "Q", **source}}
    (root / "indicators" / "IND001.yaml").write_text(yaml.safe_dump(indicator))
    (root / "datasets" / "DS_A.yaml").write_text(yaml.safe_dump(dataset))


def test_loader_reads_both_fields(tmp_path):
    write_tree(tmp_path, {"published_unit": "Mt", "value_multiplier": 1000})
    source = MetadataCatalog.load(tmp_path).dataset("DS_A").source
    assert (source.published_unit, source.value_multiplier) == ("Mt", 1000)


@pytest.mark.parametrize("bad", [0, -1, True, "1000", float("inf"), float("nan")])
def test_loader_rejects_a_multiplier_that_is_not_a_positive_finite_number(tmp_path, bad):
    write_tree(tmp_path, {"value_multiplier": bad})
    with pytest.raises(MetadataError, match="value_multiplier"):
        MetadataCatalog.load(tmp_path)


def test_loader_rejects_a_published_unit_that_is_not_text(tmp_path):
    write_tree(tmp_path, {"published_unit": 5})
    with pytest.raises(MetadataError, match="published_unit"):
        MetadataCatalog.load(tmp_path)
