"""Observation.provenance is an optional, immutable mapping with a safe default,
independent of any persistence technology."""

from types import MappingProxyType

import pytest

from sspi.errors import InvalidScoreError, SSPIError
from sspi.scoring import Observation


def test_default_provenance_is_empty_mapping():
    obs = Observation("A", "USA", 2020, 1.0, "u")
    assert obs.provenance == {}
    assert len(obs.provenance) == 0


def test_provenance_is_copied_and_immutable():
    source = {"description": "x", "nested": {"k": 1}}
    obs = Observation("A", "USA", 2020, 1.0, "u", source)
    source["description"] = "mutated"
    assert obs.provenance["description"] == "x"
    with pytest.raises(TypeError):
        obs.provenance["description"] = "y"  # type: ignore[index]
    assert isinstance(obs.provenance, MappingProxyType)


def test_provenance_equality_uses_mapping_semantics():
    a = Observation("A", "USA", 2020, 1.0, "u", {"k": 1})
    b = Observation("A", "USA", 2020, 1.0, "u", MappingProxyType({"k": 1}))
    assert a == b
    assert a.provenance == {"k": 1}


def test_provenance_must_be_a_mapping():
    with pytest.raises(SSPIError):
        Observation("A", "USA", 2020, 1.0, "u", [("k", 1)])  # type: ignore[arg-type]


def test_observation_is_hashable_despite_provenance():
    obs = Observation("A", "USA", 2020, 1.0, "u", {"k": 1})
    assert hash(obs) == hash(Observation("A", "USA", 2020, 1.0, "u", {"k": 2}))


def test_invalid_score_error_is_an_sspi_value_error():
    assert issubclass(InvalidScoreError, SSPIError)
    assert issubclass(InvalidScoreError, ValueError)
    assert str(InvalidScoreError("BIODIV/USA/2020: score must be numeric")) == "BIODIV/USA/2020: score must be numeric"
