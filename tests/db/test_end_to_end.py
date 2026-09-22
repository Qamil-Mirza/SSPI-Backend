"""The unit's success criterion:

Observation -> PostgreSQL -> Observation -> scoring kernel -> IndicatorScore -> PostgreSQL.

The metadata catalog says which datasets BIODIV needs; the repository supplies
them; the kernel scores; the repository stores the scores.
"""

from sspi.db import Repository
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation, goalpost, score_indicator


def biodiv_score(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
    return (goalpost(UNSDG_FRSHWT, 0, 100) + goalpost(UNSDG_TERRST, 0, 100) + goalpost(UNSDG_MARINE, 0, 100)) / 3


def test_observations_to_scores_through_postgres(db):
    catalog = MetadataCatalog.load()
    dataset_codes = list(catalog.indicator("BIODIV").dataset_codes)

    panel = [
        Observation("UNSDG_MARINE", "MYS", 2020, 60, "PERCENT"),
        Observation("UNSDG_TERRST", "MYS", 2020, 30, "PERCENT"),
        Observation("UNSDG_FRSHWT", "MYS", 2020, 90, "PERCENT"),
        Observation("UNSDG_MARINE", "USA", 2020, 100, "PERCENT"),
        Observation("UNSDG_TERRST", "USA", 2020, 45, "PERCENT"),
        Observation("UNSDG_FRSHWT", "USA", 2020, 120, "PERCENT"),   # clamps to 1
        Observation("UNSDG_MARINE", "KEN", 2020, 10, "PERCENT"),     # KEN lacks the other two -> unscored
        Observation("WB_POPULN", "MYS", 2020, 3.2e7, "People"),      # not a BIODIV input
    ]
    with db.transaction() as session:
        for code in {o.dataset_code for o in panel}:
            Repository(session).replace_dataset(code, [o for o in panel if o.dataset_code == code])

    with db.transaction() as session:
        repo = Repository(session)
        inputs = repo.get_observations(dataset_codes=dataset_codes, years=(2000, 2023))
        result = score_indicator(inputs, "BIODIV", biodiv_score, "Index")
        repo.replace_indicator_scores("BIODIV", result.scored)

    assert [(u.country_code, u.reason.value, u.details) for u in result.unscored] == [("KEN", "missing_datasets", ("UNSDG_TERRST", "UNSDG_FRSHWT"))]

    with db.transaction() as session:
        stored = Repository(session).get_scores(indicator_codes=["BIODIV"], countries=["MYS", "USA"], years=(2010, 2023))

    assert stored == result.scored
    by_country = {s.country_code: s for s in stored}
    assert by_country["MYS"].score == (0.9 + 0.3 + 0.6) / 3
    assert by_country["USA"].score == (1.0 + 0.45 + 1.0) / 3
    assert [o.dataset_code for o in by_country["MYS"].inputs] == ["UNSDG_FRSHWT", "UNSDG_MARINE", "UNSDG_TERRST"]
