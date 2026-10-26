"""Shared pieces of the legacy-versus-new parity tests.

The model, for every migrated dataset and indicator:

    legacy backend at the pinned commit
        -> generate_*.py, run once in the legacy virtualenv
        -> committed golden JSON next to this file
        -> offline test replaying the SAME committed source fixture
           through the new backend and comparing records

Normal test runs need neither the legacy repository nor a network.

Comparison is exact equality, floats included: both sides run the same
arithmetic in the same order on the same inputs, so any difference is a real
difference. No tolerance is applied anywhere. If a future indicator needs
one, pass it explicitly at that call site and document why in
``docs/indicator-migration.md``.

This module is deliberately small: two registers, a loader, record builders
and one comparison that explains what differs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
PINNED_LEGACY_REPOSITORY = "sspi-data-webapp"
PINNED_LEGACY_COMMIT = "76f842b08e551dfa8fb9563e4c812be086654ba6"

# The registers. A dataset is not ingestible and an indicator is not
# executable without an entry here; test_migration_gate.py enforces it.
OBSERVATION_CASES: dict[str, str] = {
    "UNSDG_MARINE": "unsdg_marine_cases.json",
    "UNSDG_TERRST": "unsdg_terrst_cases.json",
    "UNSDG_FRSHWT": "unsdg_frshwt_cases.json",
    "UNSDG_REDLST": "unsdg_redlst_cases.json",
    "UNSDG_STKHLM": "unsdg_stkhlm_cases.json",
    "UNSDG_MINMAT": "unsdg_minmat_cases.json",
    "UNSDG_MONTRL": "unsdg_montrl_cases.json",
    "UNSDG_BASELA": "unsdg_basela_cases.json",
    "UNSDG_ROTDAM": "unsdg_rotdam_cases.json",
    "UNSDG_WTSTRS": "unsdg_wtstrs_cases.json",
    "UNSDG_WUSEFF": "unsdg_wuseff_cases.json",
    "UNSDG_CWUEFF": "unsdg_cwueff_cases.json",
    "EPI_NITROG": "epi_nitrog_cases.json",
    "UNFAO_FRSTLV": "unfao_frstlv_cases.json",
    "UNFAO_FRSTAV": "unfao_frstav_cases.json",
    "UNFAO_CRBNLV": "unfao_crbnlv_cases.json",
    "UNFAO_CRBNAV": "unfao_crbnav_cases.json",
    "WID_NINCSH_PRETAX_P90P100": "wid_nincsh_pretax_p90p100_cases.json",
    "WID_NINCSH_PRETAX_P0P50": "wid_nincsh_pretax_p0p50_cases.json",
    "WB_GINIPT": "wb_ginipt_cases.json",
    "ILO_EMPLOY_TO_POP": "ilo_employ_to_pop_cases.json",
    "ILO_COLBAR": "ilo_colbar_cases.json",
    "IEA_TLCOAL": "iea_tlcoal_cases.json",
    "IEA_NATGAS": "iea_natgas_cases.json",
    "IEA_NCLEAR": "iea_nclear_cases.json",
    "IEA_HYDROP": "iea_hydrop_cases.json",
    "IEA_GEOPWR": "iea_geopwr_cases.json",
    "IEA_BIOWAS": "iea_biowas_cases.json",
    "IEA_FSLOIL": "iea_fsloil_cases.json",
    "UNSDG_NRGINT": "unsdg_nrgint_cases.json",
    "UNSDG_AIRPOL": "unsdg_airpol_cases.json",
    "UNFAO_BFPROD": "unfao_bfprod_cases.json",
    "UNFAO_BFCONS": "unfao_bfcons_cases.json",
    "WB_POPULN": "wb_populn_cases.json",
    "IEA_TCO2EM": "iea_tco2em_cases.json",
    "EPI_MSWGEN": "epi_mswgen_cases.json",  # historical parity only: no live source (UNAVAILABLE_SOURCES)
    "WB_PUPTCH": "wb_puptch_cases.json",
    "UIS_ENRPRI": "uis_enrpri_cases.json",
    "UIS_ENRSEC": "uis_enrsec_cases.json",
    "UIS_YRSEDU": "uis_yrsedu_cases.json",
    "WB_TAXREV": "wb_taxrev_cases.json",
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50": "wid_nincsh_posttax_equalsplit_p0p50_cases.json",
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100": "wid_nincsh_posttax_equalsplit_p90p100_cases.json",
    "TF_CRPTAX": "tf_crptax_cases.json",
    "UNSDG_BENFTS_UNEMP": "unsdg_benfts_unemp_cases.json",
    "ILO_FATINJ": "ilo_fatinj_cases.json",
    "UNSDG_CSTUNT": "unsdg_cstunt_cases.json",
    "WB_GDP_PERCAP_CURPRICE_USD": "wb_gdp_percap_curprice_usd_cases.json",
    "WHO_ATBRTH": "who_atbrth_synthetic_cases.json",
    "WHO_DPTCOV": "who_dptcov_synthetic_cases.json",
    "WHO_PHYSPC": "who_physpc_synthetic_cases.json",
    "WB_CREDIT": "wb_credit_cases.json",
    "WB_DPOSIT": "wb_dposit_cases.json",
    "WB_PUBACC": "wb_pubacc_cases.json",
    "WB_SANSRV": "wb_sansrv_cases.json",
    "WB_DRKWAT": "wb_drkwat_cases.json",
    "WB_AVELEC": "wb_avelec_cases.json",
    "WEF_QUELEC": "wef_quelec_synthetic_cases.json",
    "WB_MURDER": "wb_murder_cases.json",
    "ITU_CYBSEC": "itu_cybsec_synthetic_cases.json",
    "UNODC_PRIPOP": "unodc_pripop_synthetic_cases.json",
    "FSI_SECAPP": "fsi_secapp_synthetic_cases.json",
}
INDICATOR_CASES: dict[str, str] = {
    "BIODIV": "biodiv_imputation_cases.json",
    "REDLST": "redlst_cases.json",
    "CHMPOL": "chmpol_cases.json",
    "WATMAN": "watman_cases.json",
    "NITROG": "nitrog_cases.json",
    "DEFRST": "defrst_cases.json",
    "CARBON": "carbon_cases.json",
    "ISHRAT": "ishrat_cases.json",
    "GINIPT": "ginipt_cases.json",
    "EMPLOY": "employ_cases.json",
    "COLBAR": "colbar_cases.json",
    "ALTNRG": "altnrg_cases.json",
    "NRGINT": "nrgint_cases.json",
    "AIRPOL": "airpol_cases.json",
    "BEEFMK": "beefmk_cases.json",
    "COALPW": "coalpw_cases.json",
    "GTRANS": "gtrans_cases.json",
    "MSWGEN": "mswgen_cases.json",
    "PUPTCH": "puptch_cases.json",
    "ENRPRI": "enrpri_cases.json",
    "ENRSEC": "enrsec_cases.json",
    "YRSEDU": "yrsedu_cases.json",
    "TAXREV": "taxrev_cases.json",
    "TXRDST": "txrdst_cases.json",
    "CRPTAX": "crptax_cases.json",
    "UNEMPB": "unempb_cases.json",
    "FATINJ": "fatinj_cases.json",
    "CSTUNT": "cstunt_cases.json",
    "ATBRTH": "atbrth_synthetic_cases.json",
    "DPTCOV": "dptcov_synthetic_cases.json",
    "PHYSPC": "physpc_synthetic_cases.json",
    "FDEPTH": "fdepth_cases.json",
    "PUBACC": "pubacc_cases.json",
    "SANSRV": "sansrv_cases.json",
    "DRKWAT": "drkwat_cases.json",
    "AQELEC": "aqelec_synthetic_cases.json",
    "MURDER": "murder_cases.json",
    "CYBSEC": "cybsec_synthetic_cases.json",
    "PRISON": "prison_synthetic_cases.json",
    "SECAPP": "secapp_synthetic_cases.json",
}

# Golden variants on which the pinned legacy route itself cannot produce a
# result (it raises; ``legacy_impute_error`` recorded) and the new backend
# applies an APPROVED replacement policy instead. Each must point at the
# conflict entry in docs/methodology-conflicts.md that records the adopted
# policy ("Implementation policy"). Exact parity is still required for every
# variant the legacy route completes consistently.
INTENTIONAL_DIVERGENCES: dict[tuple[str, str], str] = {
    ("WATMAN", "fixture_as_committed"): "WATMAN-3",
}

# Golden variants on which the pinned legacy route completes but stores more
# than one score for one identity (``legacy_output_conflicts`` recorded:
# identities both observed and imputed, or imputed twice). Each such variant
# is registered in exactly one of the two tables below.
#
# PENDING: no replacement methodology has been approved, so the new backend
# selects NO result there: it raises ``ImputationError`` naming the conflict
# entry and writes nothing. Each must point at an unresolved entry that lays
# out the options for the methodology team without adopting one. These are
# not divergences: nothing has been chosen.
PENDING_METHODOLOGY_DECISIONS: dict[tuple[str, str], str] = {}

# RESOLVED: a methodology decision selects the result, and the conflict entry
# is resolved with cited evidence. The indicator's golden test derives the
# expected result from the legacy output by applying the decided rule
# (keeping, for every identity, the one legacy row the rule selects) and
# requires exact equality with it; no value is taken from anywhere else.
RESOLVED_METHODOLOGY_DECISIONS: dict[tuple[str, str], str] = {
    ("DEFRST", "fixture_as_committed"): "DEFRST-1",
    ("CARBON", "fixture_as_committed"): "CARBON-1",
}

# Indicators whose pinned legacy impute route exists but raises on EVERY input, whatever the data, so the
# legacy backend never stored an imputed score for them (the route deletes the indicator's stored
# imputations and then fails). The golden file records the failure at the top level (``legacy_impute_error``)
# on the fixture, on an empty dataset and on a probe written in the schema the route was written for, and
# ``imputed_scores`` is empty. The new backend reproduces what legacy persisted: observed scores only, no
# imputation strategy. This is not a replacement policy and not a divergence; each entry must point at an
# UNRESOLVED conflict entry that lays out the options for the methodology team without adopting one.
INOPERATIVE_IMPUTE_ROUTES: dict[str, str] = {
    "FDEPTH": "FDEPTH-1",
}

# Datasets whose pinned legacy cleaner could not store the source at all, repaired by a source-representation
# correction the project owner approved (country names, a missing dataset code). Nothing about values, years,
# scaling or scoring changes. The dataset's golden file records the legacy failure (``legacy_clean_error`` on the
# source or on a named variant) and the approved name table (``approved_name_corrections``); its ``observations``
# (or ``corrected_variants``) are the legacy cleaner's OWN rows with only that correction applied, accepted by the
# legacy clean collection's validation, and the indicator's golden scores are the legacy compute route's on them.
# Each entry lists every approved correction, cites the conflict entry that records the approval and says whether
# the approval is confirmed; the gate checks the files, the tables and the citation.
@dataclass(frozen=True)
class ApprovedSourceCorrection:
    conflict: str
    name_corrections: dict[str, str]  # source spelling -> ISO 3166-1 alpha-3, as approved
    other_repairs: tuple[str, ...]  # approved repairs that are not a name table
    approval: str  # who approved what, and when
    confirmed: bool


APPROVED_SOURCE_CORRECTIONS: dict[str, ApprovedSourceCorrection] = {
    "ITU_CYBSEC": ApprovedSourceCorrection(
        conflict="CYBSEC-1",
        name_corrections={"Cote d'Ivoire": "CIV", "Macedonia": "MKD", "Micronesia": "FSM", "State of Palestine": "PSE", "Vatican": "VAT"},
        other_repairs=(),
        approval="project owner, 2026-10-25: the five transcription spellings, applied only where the legacy matcher fails",
        confirmed=True,
    ),
    "FSI_SECAPP": ApprovedSourceCorrection(
        conflict="SECAPP-1",
        name_corrections={"Cote d'Ivoire": "CIV", "Macedonia": "MKD", "Micronesia": "FSM", "Palestine": "PSE", "North Korea": "PRK"},
        other_repairs=(
            "set the dataset code the legacy cleaner left out",
            "strip leading and trailing whitespace from FSI country names before ISO3 normalization",
            "map \"North Korea\" to PRK, keeping \"South Korea\" as KOR",
        ),
        approval="project owner: the FSI adapter on 2026-10-25; whitespace stripping and North Korea -> PRK confirmed on 2026-10-26",
        confirmed=True,
    ),
}

OBSERVATION_IDENTITY = ("country_code", "year")
SCORE_IDENTITY = ("country_code", "year")
IMPUTATION_FIELDS = ("imputed", "imputation_method", "imputation_distance")


def load_cases(filename: str) -> dict[str, Any]:
    """A committed golden file, verified to come from the pinned legacy commit."""
    payload = json.loads((HERE / filename).read_text())
    assert_pinned(payload, filename)
    return payload


def assert_pinned(payload: dict[str, Any], name: str) -> None:
    meta = payload.get("generated_from") or {}
    assert meta.get("repository") == PINNED_LEGACY_REPOSITORY, f"{name}: not generated from {PINNED_LEGACY_REPOSITORY}"
    assert meta.get("commit") == PINNED_LEGACY_COMMIT, f"{name}: generated from {meta.get('commit')}, not the pinned commit {PINNED_LEGACY_COMMIT}"
    assert meta.get("working_tree_dirty") is False, f"{name}: generated from a dirty legacy working tree"


def source_fixtures(payload: dict[str, Any]) -> list[Path]:
    """The committed source snapshot(s) the golden file was generated from."""
    meta = payload["generated_from"]
    names = meta.get("fixtures") or [meta["fixture"]]
    return [REPO_ROOT / name if "/" in name else REPO_ROOT / "tests" / "fixtures" / "unsdg" / name for name in names]


def legacy_failure(variant: dict[str, Any]) -> str | None:
    """The legacy route raised on this variant (candidate for INTENTIONAL_DIVERGENCES)."""
    error = variant.get("legacy_impute_error")
    return f"legacy route raised: {error}" if error else None


def legacy_output_conflict(variant: dict[str, Any]) -> str | None:
    """The legacy route completed but stored more than one score for some identity
    (candidate for PENDING_METHODOLOGY_DECISIONS)."""
    conflicts = variant.get("legacy_output_conflicts") or {}
    both = conflicts.get("observed_and_imputed") or []
    twice = conflicts.get("duplicate_imputed") or []
    if both or twice:
        return f"legacy output holds {len(both)} identities both observed and imputed and {len(twice)} imputed twice"
    return None


def legacy_inconsistency(variant: dict[str, Any]) -> str | None:
    """Why a golden variant is not parity evidence, or ``None`` when the legacy
    output is consistent and exact parity is required."""
    return legacy_failure(variant) or legacy_output_conflict(variant)


def score_level_records(scores: Iterable[Any]) -> list[dict[str, Any]]:
    """Scores as golden-file records for an indicator whose legacy route imputes
    scores: input identities and imputation fields plus the score's own
    imputation fields (legacy ``Imputed``/``ImputationMethod``/``ImputationDistance``
    on the indicator document)."""
    records = []
    for score in sorted(scores, key=lambda s: (s.country_code, s.year)):
        (record,) = score_records([score], imputation=True)
        record.update(
            imputed=bool(score.provenance.get("imputed", False)),
            imputation_method=score.provenance.get("imputation_method"),
            imputation_distance=score.provenance.get("imputation_distance"),
        )
        records.append(record)
    return records


def observation_record(observation: Any) -> dict[str, Any]:
    return {"country_code": observation.country_code, "year": observation.year, "value": observation.value, "unit": observation.unit}


def input_record(observation: Any, *, imputation: bool) -> dict[str, Any]:
    record = {"dataset_code": observation.dataset_code, "value": observation.value, "unit": observation.unit}
    if imputation:
        record = {
            "dataset_code": observation.dataset_code,
            "country_code": observation.country_code,
            "year": observation.year,
            "value": observation.value,
            "unit": observation.unit,
            "imputed": bool(observation.provenance.get("imputed", False)),
            "imputation_method": observation.provenance.get("imputation_method"),
            "imputation_distance": observation.provenance.get("imputation_distance"),
        }
    return record


def score_records(scores: Iterable[Any], *, imputation: bool) -> list[dict[str, Any]]:
    """Scores as golden-file records, sorted by identity. ``imputation=True``
    adds each input's identity and imputation fields, for indicators whose
    legacy implementation imputes."""
    return [
        {
            "country_code": s.country_code,
            "year": s.year,
            "score": s.score,
            "unit": s.unit,
            "inputs": sorted((input_record(o, imputation=imputation) for o in s.inputs), key=lambda r: r["dataset_code"]),
        }
        for s in sorted(scores, key=lambda s: (s.country_code, s.year))
    ]


def summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    years = [r["year"] for r in records]
    return {"count": len(records), "countries": sorted({r["country_code"] for r in records}), "years": (min(years), max(years)) if years else None}


def assert_parity(what: str, new: Sequence[dict[str, Any]], legacy: Sequence[dict[str, Any]], identity: Sequence[str] = SCORE_IDENTITY) -> None:
    """Exact parity of two record lists, with a failure message that says
    which identities are missing, which are extra and which fields differ.

    Both lists must already be in identity order, so order is compared too.
    """

    def key(record: dict[str, Any]) -> tuple:
        return tuple(record[name] for name in identity)

    new_by, legacy_by = {key(r): r for r in new}, {key(r): r for r in legacy}
    problems: list[str] = []
    if len(new_by) != len(new):
        problems.append(f"new backend produced {len(new) - len(new_by)} duplicate identities")
    if len(legacy_by) != len(legacy):
        problems.append(f"golden file holds {len(legacy) - len(legacy_by)} duplicate identities")
    missing, extra = sorted(set(legacy_by) - set(new_by)), sorted(set(new_by) - set(legacy_by))
    if missing:
        problems.append(f"{len(missing)} identities in legacy but not produced: {missing[:10]}")
    if extra:
        problems.append(f"{len(extra)} identities produced but not in legacy: {extra[:10]}")
    differing = [k for k in sorted(set(new_by) & set(legacy_by)) if new_by[k] != legacy_by[k]]
    for k in differing[:10]:
        fields = sorted(f for f in set(new_by[k]) | set(legacy_by[k]) if new_by[k].get(f) != legacy_by[k].get(f))
        problems.append(f"{k} differs in {fields}: " + "; ".join(f"{f} new={new_by[k].get(f)!r} legacy={legacy_by[k].get(f)!r}" for f in fields))
    if len(differing) > 10:
        problems.append(f"... and {len(differing) - 10} more differing identities")
    if not problems and list(new) != list(legacy):
        problems.append("same records in a different order")
    assert not problems, f"{what}: legacy parity broken (new {summary(new)}, legacy {summary(legacy)})\n  - " + "\n  - ".join(problems)
