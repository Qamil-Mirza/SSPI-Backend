"""Differential tests: the new imputation layer must reproduce the legacy
helpers and the legacy BIODIV impute chain exactly.

``imputation_cases.json`` and ``biodiv_imputation_cases.json`` were generated
by ``generate_imputation_cases.py`` in the old virtualenv (see
``generated_from.commit``). Values, years, method names and distances are the
legacy output verbatim; only the document shape differs. The Austria entries
are the executable legacy behaviour and conflict with the retired 2018 static
metadata; see ``methodology_conflict`` in the BIODIV file.
"""

import json
from pathlib import Path

import pytest

from sspi.errors import ImputationError
from sspi.imputation import extrapolate_backward, extrapolate_forward, impute_dataset, interpolate_linear, reference_class_average
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import CountryCatalog, MetadataCatalog
from sspi.scoring import Observation, score_indicator

HERE = Path(__file__).parent
SERIES = json.loads((HERE / "imputation_cases.json").read_text())
BIODIV = json.loads((HERE / "biodiv_imputation_cases.json").read_text())
FIXTURES = HERE.parent / "fixtures" / "unsdg"

CORE = {"DatasetCode", "CountryCode", "Year", "Value", "Unit"}
LEGACY_IMPUTATION_KEYS = {"Imputed", "ImputationMethod", "ImputationDistance"}


def to_observation(d: dict) -> Observation:
    provenance = {k: v for k, v in d.items() if k not in CORE}
    return Observation(d["DatasetCode"], d["CountryCode"], d["Year"], d["Value"], d["Unit"], provenance)


def assert_matches_legacy(new: tuple[Observation, ...], legacy: list[dict]) -> None:
    assert [(o.dataset_code, o.country_code, o.year, o.value, o.unit) for o in new] == [
        (d["DatasetCode"], d["CountryCode"], d["Year"], d["Value"], d["Unit"]) for d in legacy
    ]
    for o, d in zip(new, legacy):
        assert o.provenance["imputed"] is True and d["Imputed"] is True
        assert o.provenance["imputation_method"] == d["ImputationMethod"]
        assert o.provenance.get("imputation_distance") == d.get("ImputationDistance")
        # every non-imputation field the legacy deep copy carried is carried here too
        carried = {k: v for k, v in d.items() if k not in CORE | LEGACY_IMPUTATION_KEYS}
        assert {k: o.provenance[k] for k in carried} == carried


def test_fixtures_record_their_provenance():
    for payload in (SERIES, BIODIV):
        meta = payload["generated_from"]
        assert meta["repository"] == "sspi-data-webapp" and len(meta["commit"]) == 40 and meta["working_tree_dirty"] is False
    assert "landlocked" in BIODIV["methodology_conflict"]


# --- helpers, chained like the route --------------------------------------------------


@pytest.mark.parametrize("case", SERIES["series_cases"], ids=[c["name"] for c in SERIES["series_cases"]])
def test_series_helpers_match_legacy(case):
    observed = tuple(to_observation(d) for d in case["input"])
    backward = extrapolate_backward(observed, case["start_year"])
    assert_matches_legacy(backward, case["backward"])
    forward = extrapolate_forward(observed + backward, case["end_year"])
    assert_matches_legacy(forward, case["forward"])
    interpolated = interpolate_linear(observed + backward + forward)
    assert_matches_legacy(interpolated, case["interpolated"])
    # legacy combined list: input order, then each stage's additions
    combined = observed + backward + forward + interpolated
    assert [(o.dataset_code, o.country_code, o.year, o.value) for o in combined] == [
        (d["DatasetCode"], d["CountryCode"], d["Year"], d["Value"]) for d in case["combined"]
    ]


@pytest.mark.parametrize("case", [c for c in SERIES["series_cases"] if len({d["DatasetCode"] for d in c["input"]}) == 1], ids=lambda c: c["name"])
def test_impute_dataset_without_recipients_equals_the_chain(case):
    observed = tuple(to_observation(d) for d in case["input"])
    result = impute_dataset(observed, "DS_A", [], case["start_year"], case["end_year"])
    assert_matches_legacy(result.imputed, case["backward"] + case["forward"] + case["interpolated"])


@pytest.mark.parametrize("case", SERIES["reference_cases"], ids=[c["name"] for c in SERIES["reference_cases"]])
def test_reference_class_matches_legacy(case):
    reference = [to_observation(d) for d in case["reference"]]
    out = reference_class_average(case["target"], "DS_A", case["start"], case["end"], reference)
    assert_matches_legacy(out, case["output"])
    assert out[0].provenance["reference_observation_count"] == len(reference)


@pytest.mark.parametrize("case", SERIES["reference_errors"], ids=[c["name"] for c in SERIES["reference_errors"]])
def test_reference_class_errors_match_legacy(case):
    reference = [to_observation(d) for d in case["reference"]]
    with pytest.raises(ImputationError):
        reference_class_average(case["target"], "DS_A", case["start"], case["end"], reference)


# --- BIODIV, end to end against the legacy impute route --------------------------------


def biodiv_score(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
    return (UNSDG_MARINE + UNSDG_TERRST + UNSDG_FRSHWT) / 3 / 100  # impute route formula, verbatim


def slim(o: Observation) -> dict:
    return {
        "dataset_code": o.dataset_code,
        "country_code": o.country_code,
        "year": o.year,
        "value": o.value,
        "unit": o.unit,
        "imputed": bool(o.provenance.get("imputed", False)),
        "imputation_method": o.provenance.get("imputation_method"),
        "imputation_distance": o.provenance.get("imputation_distance"),
    }


@pytest.fixture(scope="module")
def clean():
    catalog = MetadataCatalog.load()
    payload = {
        "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
        "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
    }
    return {
        code: normalize_unsdg_dataset(catalog.dataset(code), payload[catalog.dataset(code).source.query_code]).observations
        for code in ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT")
    }


def test_declared_recipients_are_sspi67_members():
    members = CountryCatalog.load().group("SSPI67").members
    for variant in BIODIV["variants"]:
        assert set(variant["recipients"]) <= set(members)


@pytest.mark.parametrize("variant", BIODIV["variants"], ids=[v["name"] for v in BIODIV["variants"]])
def test_biodiv_chain_matches_legacy(clean, variant):
    datasets = dict(clean)
    if variant["name"] == "thinned_mys_marine":
        drop = set(range(2000, 2003)) | {2010, 2011, 2015} | set(range(2022, 2026))
        datasets["UNSDG_MARINE"] = [o for o in datasets["UNSDG_MARINE"] if not (o.country_code == "MYS" and o.year in drop)]

    scoring_input: list[Observation] = []
    for code in ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"):
        expected = variant["datasets"][code]
        result = impute_dataset(datasets[code], code, variant["recipients"], variant["start_year"], variant["end_year"])
        reference = [o for o in result.imputed if o.provenance["imputation_method"] == "ImputeReferenceClassAverage"]
        additions = [o for o in result.imputed if o not in reference]
        assert [slim(o) for o in reference] == expected["reference_rows"]
        assert sorted((slim(o) for o in additions), key=lambda s: (s["country_code"], s["imputation_method"], s["year"])) == sorted(
            expected["series_additions"], key=lambda s: (s["country_code"], s["imputation_method"], s["year"])
        )
        assert sorted({o.country_code for o in reference}) == expected["recipients_missing"]
        if reference:
            assert reference[0].value == expected["reference_mean"]
            assert reference[0].provenance["reference_observation_count"] == expected["reference_observation_count"]
        scoring_input.extend(result.combined)

    scored, unscored = score_indicator(scoring_input, "BIODIV", biodiv_score, "Index")
    assert len(scored) == variant["scored_count"]
    assert sorted({(g.country_code, g.year) for g in unscored}) == [tuple(x) for x in variant["incomplete_identities"]]

    imputed = sorted((s for s in scored if any(o.provenance.get("imputed") for o in s.inputs)), key=lambda s: (s.country_code, s.year))
    got = [
        {"country_code": s.country_code, "year": s.year, "score": s.score, "unit": s.unit, "inputs": sorted((slim(o) for o in s.inputs), key=lambda x: x["dataset_code"])}
        for s in imputed
    ]
    assert got == variant["imputed_scores"]
    observed_only = sorted({(s.country_code, s.year) for s in scored if not any(o.provenance.get("imputed") for o in s.inputs)})
    assert observed_only == [tuple(x) for x in variant["observed_only_scores_not_stored_by_impute_route"]]


def test_austria_and_malaysia_headline_values():
    """Executable legacy result, labelled as conflicting with the retired static metadata."""
    committed = next(v for v in BIODIV["variants"] if v["name"] == "fixture_as_committed")
    aut = next(s for s in committed["imputed_scores"] if s["country_code"] == "AUT" and s["year"] == 2020)
    marine = next(i for i in aut["inputs"] if i["dataset_code"] == "UNSDG_MARINE")
    assert marine["imputed"] and marine["imputation_method"] == "ImputeReferenceClassAverage"
    assert marine["value"] == 36.56867346153846 == committed["datasets"]["UNSDG_MARINE"]["reference_mean"]
    assert aut["score"] == 0.5858737782051282
    assert [s["year"] for s in committed["imputed_scores"] if s["country_code"] == "AUT"] == list(range(2000, 2024))
    assert not any(s["country_code"] == "MYS" for s in committed["imputed_scores"])  # complete series: nothing imputed
    assert ["MYS", 2020] in committed["observed_only_scores_not_stored_by_impute_route"]
