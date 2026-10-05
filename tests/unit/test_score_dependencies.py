"""The generic indicator-score dependency mechanism: declaration and
validation on ``IndicatorDefinition``, delivery through the imputation
context, and the rule that a missing dependency stops the run. Exercised with
a made-up indicator so nothing here depends on GINIPT."""

import inspect
from dataclasses import dataclass

import pytest

from sspi.errors import IndicatorDefinitionError, InvalidObservationError, ScoreDependencyError, UnknownCodeError
from sspi.indicators import IndicatorDefinition, compute_indicator, registry, runner
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult
from sspi.metadata import MetadataCatalog
from sspi.scoring import IndicatorScore, Observation


def score_x(UNSDG_REDLST):  # noqa: N803
    return UNSDG_REDLST


@dataclass(frozen=True)
class Recording:
    """A strategy that records the context it was given and imputes nothing."""

    seen: list
    auxiliary_datasets: tuple = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        self.seen.append(context)
        return IndicatorImputationResult((), tuple(context.observed_unscored))


def definition(dependencies=("ISHRAT",), seen=None):
    return IndicatorDefinition("REDLST", score_x, imputation=Recording([] if seen is None else seen), score_dependencies=dependencies)


def dep(code, country, year, score=0.5):
    return IndicatorScore(code, country, year, score, "u", ())


OBSERVATIONS = [Observation("UNSDG_REDLST", "MYS", 2020, 0.8, "Index")]


def test_declaration_is_validated():
    assert IndicatorDefinition("REDLST", score_x).score_dependencies == ()
    for bad in (["ISHRAT"], ("",), (1,), "ISHRAT"):
        with pytest.raises(IndicatorDefinitionError, match="tuple of indicator codes"):
            definition(bad)
    with pytest.raises(IndicatorDefinitionError, match="distinct indicators other than itself"):
        definition(("ISHRAT", "ISHRAT"))
    with pytest.raises(IndicatorDefinitionError, match="distinct indicators other than itself"):
        definition(("REDLST",))
    with pytest.raises(IndicatorDefinitionError, match="imputation strategy"):
        IndicatorDefinition("REDLST", score_x, imputation=None, score_dependencies=("ISHRAT",))


def test_check_against_requires_dependencies_to_be_catalog_indicators():
    catalog = MetadataCatalog.load()
    definition(("ISHRAT",)).check_against(catalog)
    with pytest.raises(UnknownCodeError):
        definition(("NOSUCH",)).check_against(catalog)


def test_every_registered_dependency_is_itself_executable():
    for code in registry.codes():
        for dependency in registry.get(code).score_dependencies:
            assert dependency in registry.codes(), f"{code} depends on {dependency}, which cannot be run"
    assert {code: registry.get(code).score_dependencies for code in registry.codes() if registry.get(code).score_dependencies} == {"GINIPT": ("ISHRAT",)}


def test_scores_reach_the_strategy_sorted_and_read_only():
    seen = []
    supplied = [dep("ISHRAT", "MYS", 2021), dep("ISHRAT", "AUT", 2020), dep("ISHRAT", "MYS", 2020)]
    compute_indicator(definition(seen=seen), OBSERVATIONS, dependency_scores={"ISHRAT": supplied})
    (context,) = seen
    assert list(context.dependency_scores) == ["ISHRAT"]
    assert [(s.country_code, s.year) for s in context.dependency_scores["ISHRAT"]] == [("AUT", 2020), ("MYS", 2020), ("MYS", 2021)]
    with pytest.raises(TypeError):
        context.dependency_scores["ISHRAT"] = ()


def test_a_missing_or_empty_dependency_stops_the_run_with_a_clear_message():
    seen = []
    for supplied in (None, {}, {"ISHRAT": []}):
        with pytest.raises(ScoreDependencyError) as info:
            compute_indicator(definition(seen=seen), OBSERVATIONS, dependency_scores=supplied)
        message = str(info.value)
        assert "REDLST requires existing ISHRAT scores" in message and "Run ISHRAT first" in message and "Nothing was computed or written" in message
    assert seen == []  # the strategy was never called


def test_undeclared_and_misfiled_scores_are_refused():
    with pytest.raises(InvalidObservationError, match="does not depend on"):
        compute_indicator(definition(), OBSERVATIONS, dependency_scores={"ISHRAT": [dep("ISHRAT", "MYS", 2020)], "BIODIV": [dep("BIODIV", "MYS", 2020)]})
    with pytest.raises(InvalidObservationError, match="does not depend on"):
        compute_indicator(registry.get("REDLST"), OBSERVATIONS, dependency_scores={"ISHRAT": [dep("ISHRAT", "MYS", 2020)]})
    with pytest.raises(InvalidObservationError, match="belong to"):
        compute_indicator(definition(), OBSERVATIONS, dependency_scores={"ISHRAT": [dep("BIODIV", "MYS", 2020)]})


def test_indicators_without_dependencies_get_an_empty_mapping_and_behave_as_before():
    seen = []
    plain = IndicatorDefinition("REDLST", score_x, imputation=Recording(seen))
    result = compute_indicator(plain, OBSERVATIONS)
    assert seen[0].dependency_scores == {} and [(s.country_code, s.score) for s in result.scores] == [("MYS", 0.8)]
    assert compute_indicator(plain, OBSERVATIONS, dependency_scores={}).scores == result.scores
    for code in ("BIODIV", "REDLST", "CHMPOL", "WATMAN", "NITROG", "DEFRST", "CARBON", "ISHRAT"):
        assert registry.get(code).score_dependencies == ()


def test_the_generic_layers_name_no_indicator():
    """The mechanism is declared by definitions and carried by the runner; the runner, the registry's definition class
    and the strategy module's context know no indicator code."""
    from sspi.indicators import strategy

    sources = [inspect.getsource(runner), inspect.getsource(IndicatorDefinition), inspect.getsource(strategy.IndicatorImputationContext), inspect.getsource(strategy.regression_impute_scores), inspect.getsource(strategy.fit_centered_least_squares)]
    for source in sources:
        code_only = "\n".join(line for line in source.splitlines() if not line.strip().startswith(("#", '"', "*", "-")))
        assert "GINIPT" not in code_only and "ISHRAT" not in code_only
