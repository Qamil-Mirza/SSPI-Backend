"""Generate the Infrastructure golden files from the committed source fixtures:

    wb_sansrv_cases.json, sansrv_cases.json
    wb_drkwat_cases.json, drkwat_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_infrastructure_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed World Bank samples (one raw document
per API row); the ``compute_sansrv``, ``impute_sansrv`` and
``compute_drkwat`` view functions run unwrapped from their decorators with
their collection handles replaced by ``MongoStub`` collections whose
``insert_many`` first applies the legacy collections' own document
validation (``validate_documents_format``, which rejects a score outside
[0, 1]), so a route that legacy could not store fails here too.

The SANSRV route is also run on a variant of the committed sample with a
few clean rows removed (``removed_observations``): Malaysia 2010-2012, an
interior gap, and Turks and Caicos 2017-2024, which leaves a single
observed year. The live series has neither, and the variant shows what the
legacy impute route does with them. Rows are only removed; no value is
invented.

The goalposts the routes read from metadata at runtime come from the
pinned methodology files.

Three other Infrastructure leaves are checked, not generated:

* TRNETW: no compute or impute view exists (the route file holds one
  import), and no cleaner exists for its datasets;
* INTRNT: its compute route reads ``WB_INTRNT`` and ``UNSDG_INTRNT``, which
  the canonical metadata does not list, and averages the raw values; the
  legacy indicator collection rejects the resulting scores (see
  docs/methodology-conflicts.md, INTRNT-1). It is not ported, so nothing is
  generated;
* AQELEC: its WEF input needs a source adapter that is not approved
  (AQELEC-1).
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_education_cases import source_rows
from generate_inequality_cases import identities, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub
from legacy_stubs import MongoStub, legacy_skipped

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
FIXTURES = {
    "WB_SANSRV": ("SH.STA.BASS.ZS", "tests/fixtures/wb/SH.STA.BASS.ZS_sample.json"),
    "WB_DRKWAT": ("SH.H2O.SMDW.ZS", "tests/fixtures/wb/SH.H2O.SMDW.ZS_sample.json"),
}
# Clean rows removed for the SANSRV variant: (country, year)
SANSRV_REMOVED = {("MYS", 2010), ("MYS", 2011), ("MYS", 2012), *(("TCA", year) for year in range(2017, 2025))}


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "pg", "inf", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def validating(name, legacy_collection, documents=()):
    """A MongoStub whose inserts are first checked the way the legacy collection checked them."""

    class Validating(MongoStub):
        def insert_many(self, docs):
            legacy_collection.validate_documents_format(docs)
            return super().insert_many(docs)

    return Validating(name, documents)


def main() -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.models.database import sspi_imputed_data, sspi_indicator_data

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = MetadataStub()
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixture": fixture,
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    # ------------------------------------------------------------ TRNETW: nothing executable
    trnetw = importlib.import_module("sspi_flask_app.api.core.sspi.pg.inf.trnetw")
    assert not [name for name in vars(trnetw) if "trnetw" in name.lower()], "TRNETW now defines a view function"
    assert not {"WB_RAILNT", "CIA_ROADNT"} & set(dataset_cleaner_registry)
    print("TRNETW: no compute or impute view; WB_RAILNT and CIA_ROADNT have no cleaner")

    # ------------------------------------------------------------ the two World Bank datasets
    clean = {}
    for code, (series, fixture) in FIXTURES.items():
        rows = source_rows("WB", fixture)
        module = importlib.import_module(f"sspi_flask_app.api.core.datasets.wb.{code.lower()}")
        module.sspi_raw_api_data = RawStub(rows)
        module.sspi_clean_api_data, module.sspi_metadata = CleanStub(), metadata
        cleaned = dataset_cleaner_registry[code]()
        assert cleaned and all(d["DatasetCode"] == code for d in cleaned), code
        clean[code] = cleaned
        skipped, without_code, missing = legacy_skipped(rows)
        observations = observation_records(cleaned)
        write(
            f"{code.lower()}_cases.json",
            {
                "generated_from": generated_from([f"{module.__name__}.{dataset_cleaner_registry[code].__name__} (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], fixture),
                "dataset_code": code,
                "source_indicator": series,
                "observations": observations,
                "descriptions": sorted({d["Description"] for d in cleaned}),
                "skipped_areas": skipped,
                "rows_without_area_code": without_code,
                "empty_source_values": missing,
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        years = [o["year"] for o in observations]
        print(f"{code}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {missing} missing values")

    # ------------------------------------------------------------------- SANSRV
    module = importlib.import_module("sspi_flask_app.api.core.sspi.pg.inf.sansrv")
    module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata

    def sansrv(clean_documents):
        module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
        module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
        module.sspi_imputed_data = validating("sspi_imputed_data", sspi_imputed_data)
        observed = unwrap(module.compute_sansrv)()
        try:
            imputed, error = unwrap(module.impute_sansrv)(), None
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            imputed, error = [], f"{type(exc).__name__}: {exc}"
        assert len(module.sspi_indicator_data.documents) == len(observed) and len(module.sspi_imputed_data.documents) == len(imputed)
        observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
        counts = {}
        for d in imputed:
            counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
        return observed, imputed, error, {
            "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
            "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
        }

    observed, imputed, error, conflicts = sansrv(clean["WB_SANSRV"])
    variant_rows = [d for d in clean["WB_SANSRV"] if (d["CountryCode"], d["Year"]) not in SANSRV_REMOVED]
    assert len(clean["WB_SANSRV"]) - len(variant_rows) == len(SANSRV_REMOVED)
    v_observed, v_imputed, v_error, v_conflicts = sansrv(variant_rows)
    empty_observed, _, empty_error, _ = sansrv([])
    front = frontmatter("SANSRV")
    lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
    (observed_unit,) = {d["Unit"] for d in observed}
    (imputed_unit,) = {d["Unit"] for d in imputed}
    write(
        "sansrv_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner function for WB_SANSRV (Mongo handles stubbed)",
                    f"{module.__name__}.compute_sansrv (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                    f"{module.__name__}.impute_sansrv (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                ],
                FIXTURES["WB_SANSRV"][1],
            ),
            "indicator_code": "SANSRV",
            "formula": f"goalpost(WB_SANSRV, {lg}, {ug})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"].strip(),
            "goalposts": [lg, ug],
            "unit": observed_unit,
            "imputed_unit": imputed_unit,
            "impute_route_exists": True,
            "series_fill": {"forward_to": 2023, "backward_to": 2000, "interpolation": None, "order": ["forward", "backward"], "series_id": ["CountryCode", "DatasetCode"]},
            "observed_scores": records(observed, imputation=True),
            "imputed_scores": records(imputed, imputation=True),
            "legacy_impute_error": error,
            "legacy_output_conflicts": conflicts,
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=True), "legacy_impute_error": empty_error},
            "variants": [
                {
                    "name": "with_rows_removed",
                    "removed_observations": [list(r) for r in sorted(SANSRV_REMOVED)],
                    "observed_scores": records(v_observed, imputation=True),
                    "imputed_scores": records(v_imputed, imputation=True),
                    "legacy_impute_error": v_error,
                    "legacy_output_conflicts": v_conflicts,
                }
            ],
        },
    )
    fill_years = [d["Year"] for d in imputed]
    print(
        f"SANSRV: {len(observed)} observed ({min(d['Year'] for d in observed)}-{max(d['Year'] for d in observed)}, unit {observed_unit!r}), "
        f"{len(imputed)} imputed ({min(fill_years)}-{max(fill_years)}, unit {imputed_unit!r}), conflicts {conflicts}; "
        f"variant: {len(v_observed)} observed, {len(v_imputed)} imputed; empty: {len(empty_observed)} observed, impute error {empty_error}"
    )

    # ------------------------------------------------------------------- DRKWAT
    module = importlib.import_module("sspi_flask_app.api.core.sspi.pg.inf.drkwat")
    module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata
    module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean["WB_DRKWAT"])
    module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
    observed = unwrap(module.compute_drkwat)()
    module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data"), validating("sspi_indicator_data", sspi_indicator_data)
    empty_observed = unwrap(module.compute_drkwat)()
    front = frontmatter("DRKWAT")
    (observed_unit,) = {d["Unit"] for d in observed}
    write(
        "drkwat_cases.json",
        {
            "generated_from": generated_from(
                ["registered @dataset_cleaner function for WB_DRKWAT (Mongo handles stubbed)", f"{module.__name__}.compute_drkwat (unwrapped view function, collection handles stubbed, legacy insert validation applied)"],
                FIXTURES["WB_DRKWAT"][1],
            ),
            "indicator_code": "DRKWAT",
            "formula": f"goalpost(WB_DRKWAT, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"].strip(),
            "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
            "unit": observed_unit,
            "impute_route_exists": hasattr(module, "impute_drkwat"),
            "scores": records(observed, imputation=False),
            "incomplete_identities": identities([]),
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
        },
    )
    years = [d["Year"] for d in observed]
    print(f"DRKWAT: {len(observed)} scores ({min(years)}-{max(years)}, unit {observed_unit!r}), impute route: {hasattr(module, 'impute_drkwat')}")


if __name__ == "__main__":
    main()
