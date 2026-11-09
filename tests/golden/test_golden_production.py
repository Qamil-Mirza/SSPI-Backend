"""Parity with legacy production for the indicators in ``PRODUCTION_PRECEDENCE``.

The project owner decided on 2026-11-09 that where the pinned legacy commit and
production (https://sspi.world) disagree, production takes precedence. For
MSWGEN (MSWGEN-1) and BIODIV (BIODIV-6) they disagree: production serves output
of legacy code older than the pinned commit. Here the registered definitions
run on production's own clean rows (``tests/fixtures/production``, from the
2026-11-09 snapshot of the public API) and must reproduce production's own
scores exactly: every observed score, and every score of the aggregation
window (SSPI67 x 2000-2023) with its observed/imputed classification. The
goldens are production output (``generate_production_cases.py``), not legacy
code output.

The pinned commit's behaviour is kept (``pinned_reference``) and stays exactly
parity-tested in ``test_golden_biodiv_orchestration.py`` and
``test_golden_mswgen.py``; the difference between the two is characterized
below.
"""

import dataclasses
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from sspi.imputation import REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.biodiv import PINNED_IMPUTATION, PRODUCTION_REFERENCE_COUNTRIES
from sspi.indicators.mswgen import PINNED_GOALPOSTS
from sspi.metadata import CountryCatalog
from sspi.scoring import Observation, goalpost
from tests.golden.parity import HERE, PRODUCTION_PRECEDENCE, REPO_ROOT

LEGACY = Path(os.environ.get("SSPI_LEGACY_REPO", REPO_ROOT.parent / "sspi-data-webapp"))


def golden(code):
    return json.loads((HERE / PRODUCTION_PRECEDENCE[code].production_golden).read_text(encoding="utf-8"))


def production_observations(code):
    case = golden(code)
    rows = json.loads((REPO_ROOT / case["source_fixture"]).read_text(encoding="utf-8"))
    return [Observation(r["DatasetCode"], r["CountryCode"], r["Year"], r["Value"], r["Unit"]) for r in rows if r["DatasetCode"] in case["dataset_codes"]]


def run(definition, observations):
    recipients = CountryCatalog.load().group(definition.recipient_group).members if definition.recipient_group else ()
    return compute_indicator(definition, observations, recipients)


@pytest.fixture(scope="module", params=sorted(PRODUCTION_PRECEDENCE))
def code(request):
    return request.param


def test_the_fixture_is_the_one_the_golden_was_generated_from(code):
    case = golden(code)
    fixture = REPO_ROOT / case["source_fixture"]
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == case["source_fixture_sha256"]
    assert case["indicator_code"] == code and tuple(case["dataset_codes"]) == registry.get(code).dataset_codes


def test_observed_scores_match_production_exactly(code):
    case = golden(code)
    result = run(registry.get(code), production_observations(code))
    new = {(s.country_code, s.year): (s.score, s.unit) for s in result.observed_scores}
    expected = {(r["country_code"], r["year"]): (r["score"], r["unit"]) for r in case["observed_scores"]}
    assert new == expected


def test_the_aggregation_window_matches_production_exactly_with_its_classification(code):
    case = golden(code)
    result = run(registry.get(code), production_observations(code))
    new = {(s.country_code, s.year): (s.score, is_imputed(s)) for s in result.scores}
    expected = {(r["country_code"], r["year"]): (r["score"], r["imputed"]) for r in case["window_scores"]}
    assert {key: new.get(key) for key in expected} == expected
    countries, (start, end) = set(case["window"]["countries"]), case["window"]["years"]
    imputed_in_window = {(s.country_code, s.year) for s in result.imputed_scores if s.country_code in countries and start <= s.year <= end}
    assert imputed_in_window == {key for key, (_, imputed) in expected.items() if imputed}
    assert len(expected) == len(countries) * (end - start + 1) == 66 * 24


# --- MSWGEN: production's goalposts, the pinned commit's reversed ----------------------------


def test_mswgen_production_is_the_pinned_score_reversed():
    observations = production_observations("MSWGEN")
    production = {(s.country_code, s.year): s.score for s in run(registry.get("MSWGEN"), observations).scores}
    assert registry.get("MSWGEN").goalposts == (0, 100) and PINNED_GOALPOSTS == (100, 0)
    for o in observations:
        assert production[(o.country_code, o.year)] == goalpost(o.value, 0, 100)
        assert production[(o.country_code, o.year)] == pytest.approx(1 - goalpost(o.value, *PINNED_GOALPOSTS), abs=1e-12)
    assert (production[("USA", 2020)], production[("DNK", 2020)], production[("ETH", 2020)]) == (0.133, 0.129, 0.892)


# --- BIODIV: production's impute route against the pinned commit's ---------------------------


def test_biodiv_differs_from_the_pinned_route_only_in_the_listed_countries_imputed_scores():
    observations = production_observations("BIODIV")
    production = run(registry.get("BIODIV"), observations)
    pinned = run(dataclasses.replace(registry.get("BIODIV"), imputation=PINNED_IMPUTATION), observations)
    assert production.observed_scores == pinned.observed_scores  # the compute route is the same
    listed = set(PRODUCTION_REFERENCE_COUNTRIES)
    p = {(s.country_code, s.year): s.score for s in production.imputed_scores}
    q = {(s.country_code, s.year): s.score for s in pinned.imputed_scores}
    # everyone else: identical imputed scores (in production's data the pinned route's SSPI67 recipients with no rows
    # are listed countries, so it gives nobody else a reference value either)
    assert {k: v for k, v in p.items() if k[0] not in listed} == {k: v for k, v in q.items() if k[0] not in listed}
    assert p.keys() == q.keys()
    differing = {k for k in p if p[k] != q[k]}
    assert differing == {(c, y) for c in listed for y in range(2000, 2024)}


def test_the_listed_countries_get_one_constant_from_the_other_countries_means():
    observations = production_observations("BIODIV")
    result = run(registry.get("BIODIV"), observations)
    listed = set(PRODUCTION_REFERENCE_COUNTRIES)
    means = {}
    for code in ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"):
        values = [o.value for o in observations if o.dataset_code == code and o.country_code not in listed]
        means[code] = sum(values) / len(values)
    expected = (means["UNSDG_MARINE"] + means["UNSDG_TERRST"] + means["UNSDG_FRSHWT"]) / 3 / 100
    listed_scores = [s for s in result.imputed_scores if s.country_code in listed]
    assert len(listed_scores) == 9 * 24 and {s.score for s in listed_scores} == {expected} == {0.4073736631496143}
    aut = next(s for s in listed_scores if (s.country_code, s.year) == ("AUT", 2010))
    assert {o.dataset_code: (o.value, o.provenance["imputation_method"]) for o in aut.inputs} == {code: (means[code], REFERENCE_CLASS_AVERAGE) for code in means}
    assert any(o.country_code == "AUT" and o.dataset_code == "UNSDG_TERRST" for o in observations)  # Austria's own rows exist and are not used


@pytest.mark.skipif(not (LEGACY / ".git").exists(), reason="legacy repository not checked out next to this one")
def test_the_hard_coded_list_is_the_legacy_routes_verbatim():
    change = PRODUCTION_PRECEDENCE["BIODIV"].superseded_legacy_change
    source = subprocess.run(
        ["git", "-C", str(LEGACY), "show", f"{change}^:sspi_flask_app/api/core/sspi/sus/eco/biodiv.py"], capture_output=True, text=True, check=True
    ).stdout
    line = next(line for line in source.splitlines() if line.strip().startswith("countries_no_data = "))
    assert line.strip() == "countries_no_data = " + json.dumps(list(PRODUCTION_REFERENCE_COUNTRIES))


def test_a_listed_countrys_observed_score_outside_the_imputation_years_is_kept():
    """BIODIV-6: only 2000-2023 is imputed, so an observed score of a listed country in 2024 collides with nothing."""
    complete_2024 = [Observation(code, "AUT", 2024, value, "PERCENT") for code, value in (("UNSDG_MARINE", 10.0), ("UNSDG_TERRST", 20.0), ("UNSDG_FRSHWT", 30.0))]
    observations = [o for o in production_observations("BIODIV") if (o.country_code, o.year) != ("AUT", 2024)] + complete_2024
    result = run(registry.get("BIODIV"), observations)
    aut = {s.year: s for s in result.scores if s.country_code == "AUT"}
    assert not is_imputed(aut[2024]) and aut[2024].score == pytest.approx(0.2)
    assert all(is_imputed(aut[y]) and aut[y].score == 0.4073736631496143 for y in range(2000, 2024))
