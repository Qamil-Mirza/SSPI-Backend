"""Score-level provenance (migration 0003): stored exactly, classified
correctly, verified on read. The persisted ``imputed`` boolean stays derived:
from the score's own provenance or from an imputed input, never supplied."""

import json

import pytest
from sqlalchemy import text

from sspi.db import Repository
from sspi.errors import InvalidScoreError, ScoreIntegrityError
from sspi.imputation import is_imputed
from sspi.scoring import IndicatorScore, Observation


def obs(country="MYS", year=2020, value=50.0, **provenance):
    return Observation("UNFAO_FRSTLV", country, year, value, "1000 ha", provenance)


def score(country="MYS", year=2020, value=0.5, inputs=None, provenance=None):
    inputs = (obs(country, year),) if inputs is None else tuple(inputs)
    return IndicatorScore("DEFRST", country, year, value, "Index", inputs, (), provenance or {})


EXTRAPOLATED = {"imputed": True, "imputation_method": "ExtrapolateForward", "source_year": 2020, "imputation_distance": 3}
REFERENCE = {"imputed": True, "imputation_method": "ImputeReferenceClassAverage", "reference_score_count": 184}


def stored(db):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, imputed, provenance FROM indicator_score ORDER BY 1, 2")).all()


def test_classification_rule():
    assert is_imputed(score()) is False
    assert is_imputed(score(inputs=[obs(imputed=True, imputation_method="Linear Interpolation")])) is True
    assert is_imputed(score(provenance=EXTRAPOLATED)) is True
    assert is_imputed(score(provenance={"imputed": False, "note": "explicitly observed"})) is False
    assert is_imputed(score(provenance={"imputation_method": "ExtrapolateForward"})) is False  # only the flag counts


def test_provenance_is_copied_and_frozen():
    source = {"imputed": True, "imputation_method": "ExtrapolateForward"}
    s = score(provenance=source)
    source["imputed"] = False
    assert s.provenance["imputed"] is True
    with pytest.raises(TypeError):
        s.provenance["imputed"] = False  # type: ignore[index]
    assert json.loads(json.dumps(dict(s.provenance))) == dict(s.provenance)


def test_three_kinds_of_score_persist_with_the_derived_flag(db):
    scores = [
        score("MYS", 2020),
        score("AUT", 2020, inputs=[obs("AUT", 2020, imputed=True, imputation_method="ImputeReferenceClassAverage")]),
        score("MYS", 2023, inputs=[obs("MYS", 2020)], provenance=EXTRAPOLATED),  # copied inputs keep their real year; source_year says why
        score("BEL", 2020, inputs=[], provenance=REFERENCE),
    ]
    with db.transaction() as session:
        assert Repository(session).save_scores(scores) == 4
    assert [tuple(r) for r in stored(db)] == [("AUT", 2020, True, {}), ("BEL", 2020, True, REFERENCE), ("MYS", 2020, False, {}), ("MYS", 2023, True, EXTRAPOLATED)]
    with db.transaction() as session:
        loaded = {(s.country_code, s.year): s for s in Repository(session).get_scores(indicator_codes=["DEFRST"])}
    assert dict(loaded[("MYS", 2023)].provenance) == EXTRAPOLATED and loaded[("MYS", 2023)].inputs[0].year == 2020
    assert dict(loaded[("BEL", 2020)].provenance) == REFERENCE and loaded[("BEL", 2020)].inputs == ()
    assert dict(loaded[("MYS", 2020)].provenance) == {} and dict(loaded[("AUT", 2020)].provenance) == {}
    assert [is_imputed(loaded[k]) for k in sorted(loaded)] == [True, True, False, True]
    with db.transaction() as session:
        assert Repository(session).get_scores(indicator_codes=["DEFRST"], imputed=True) and len(Repository(session).get_scores(indicator_codes=["DEFRST"], imputed=False)) == 1


def test_provenance_survives_the_round_trip_exactly(db):
    provenance = {"imputed": True, "imputation_method": "ExtrapolateForward", "source_year": 2019, "imputation_distance": 4, "notes": ["a", 1, 2.5, None], "nested": {"k": [1, 2]}}
    with db.transaction() as session:
        Repository(session).save_scores([score(provenance=provenance)])
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
    assert dict(loaded.provenance) == provenance


def test_non_json_provenance_is_rejected_before_any_write(db):
    with pytest.raises(InvalidScoreError, match="provenance"):
        with db.transaction() as session:
            Repository(session).save_scores([score(provenance={"imputed": True, "when": object()})])
    assert stored(db) == []


def test_tampered_boolean_fails_on_read(db):
    with db.transaction() as session:
        Repository(session).save_scores([score(provenance=EXTRAPOLATED)])
        session.execute(text("UPDATE indicator_score SET imputed = false"))
    with pytest.raises(ScoreIntegrityError, match="stored imputed=False but the embedded provenance and inputs classify the score as imputed"):
        with db.transaction() as session:
            Repository(session).get_scores()


def test_tampered_provenance_fails_on_read(db):
    with db.transaction() as session:
        Repository(session).save_scores([score(provenance=EXTRAPOLATED)])
        session.execute(text("""UPDATE indicator_score SET provenance = provenance || '{"imputed": false}'::jsonb"""))
    with pytest.raises(ScoreIntegrityError, match="stored imputed=True"):
        with db.transaction() as session:
            Repository(session).get_scores()


def test_old_style_row_without_provenance_is_readable(db):
    with db.transaction() as session:
        session.execute(
            text(
                "INSERT INTO indicator_score (indicator_code, country_code, year, score, unit, inputs, imputed) VALUES "
                "('DEFRST', 'MYS', 2020, 0.5, 'Index', :inputs, false)"
            ),
            {"inputs": json.dumps({"observations": [{"dataset_code": "UNFAO_FRSTLV", "country_code": "MYS", "year": 2020, "value": 1.0, "unit": "1000 ha", "provenance": {}}], "computed": []})},
        )
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
    assert dict(loaded.provenance) == {} and is_imputed(loaded) is False


def test_observed_still_wins_over_score_level_imputed_in_save_scores(db):
    with db.transaction() as session:
        Repository(session).save_scores([score("MYS", 2023, value=0.4)])
        assert Repository(session).save_scores([score("MYS", 2023, value=0.9, provenance=EXTRAPOLATED)]) == 0
        (loaded,) = Repository(session).get_scores()
    assert loaded.score == 0.4 and dict(loaded.provenance) == {}
