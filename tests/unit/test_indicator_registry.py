"""The executable indicator registry: code -> IndicatorDefinition, validated
against the canonical metadata. Minimal by design: a literal mapping."""

import pytest

from sspi.errors import IndicatorDefinitionError, MetadataError, UnknownCodeError
from sspi.indicators import IndicatorDefinition, registry
from sspi.indicators.strategy import ImputationStrategy, ImputeInputsThenScore
from sspi.metadata import MetadataCatalog


def test_biodiv_resolves_to_an_executable_definition():
    definition = registry.get("BIODIV")
    assert isinstance(definition, IndicatorDefinition)
    assert definition.code == "BIODIV"
    assert callable(definition.observed_score) and definition.unit == "Index"
    assert isinstance(definition.imputation, ImputeInputsThenScore) and isinstance(definition.imputation, ImputationStrategy)
    assert definition.imputation.years == (2000, 2023) and definition.imputation.recipient_group == "SSPI67"
    assert definition.recipient_group == "SSPI67" and definition.auxiliary_datasets == () and definition.imputes


def test_indicators_without_a_legacy_impute_route_have_no_strategy():
    for code in ("REDLST", "CHMPOL"):
        definition = registry.get(code)
        assert definition.imputation is None and not definition.imputes
        assert definition.recipient_group is None and definition.auxiliary_datasets == ()


def test_registered_codes_are_listed():
    assert registry.codes() == ("BIODIV", "REDLST", "CHMPOL", "WATMAN", "NITROG", "DEFRST", "CARBON")


@pytest.mark.parametrize("code", ["AIRPOL", "biodiv", "", "NOPE"])
def test_unknown_or_unimplemented_code_raises_a_clear_error(code):
    with pytest.raises(UnknownCodeError, match="no executable definition") as info:
        registry.get(code)
    assert repr(code) in str(info.value)


def test_dependencies_are_the_score_function_parameter_names():
    definition = registry.get("BIODIV")
    assert definition.dataset_codes == ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT")


def test_every_registered_definition_agrees_with_the_bundled_metadata():
    catalog = MetadataCatalog.load()
    for code in registry.codes():
        registry.get(code).check_against(catalog)  # must not raise


def test_definition_whose_callables_disagree_with_metadata_fails_clearly():
    def formula(UNSDG_MARINE, UNSDG_TERRST, EXTRA):
        return 0.0

    definition = IndicatorDefinition("BIODIV", formula)
    with pytest.raises(IndicatorDefinitionError) as info:
        definition.check_against(MetadataCatalog.load())
    message = str(info.value)
    assert "BIODIV" in message and "UNSDG_FRSHWT" in message and "EXTRA" in message
    assert isinstance(info.value, MetadataError)


def test_imputation_must_be_a_strategy():
    def f(A):
        return 0.0

    with pytest.raises(IndicatorDefinitionError, match="ImputationStrategy"):
        IndicatorDefinition("X", f, imputation=f)  # a bare callable is not a strategy


def test_auxiliary_datasets_must_be_distinct_and_not_dependencies():
    def f(A):
        return 0.0

    class Strategy:
        auxiliary_datasets = ("A",)
        recipient_group = None

        def impute(self, context):
            raise AssertionError

    with pytest.raises(IndicatorDefinitionError, match="auxiliary"):
        IndicatorDefinition("X", f, imputation=Strategy())


def test_check_against_requires_auxiliary_datasets_to_exist_in_the_catalog():
    def f(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        return 0.0

    class Strategy:
        auxiliary_datasets = ("NOT_A_DATASET",)
        recipient_group = None

        def impute(self, context):
            raise AssertionError

    with pytest.raises(UnknownCodeError):
        IndicatorDefinition("BIODIV", f, imputation=Strategy()).check_against(MetadataCatalog.load())


def test_definition_for_a_code_unknown_to_metadata_fails_clearly():
    def f(UNSDG_MARINE):
        return 0.0

    with pytest.raises(UnknownCodeError):
        IndicatorDefinition("NOTREAL", f).check_against(MetadataCatalog.load())


def test_definitions_are_immutable():
    with pytest.raises(AttributeError):
        registry.get("BIODIV").unit = "x"
