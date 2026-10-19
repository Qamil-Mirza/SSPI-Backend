"""Generate the WHO Healthcare golden files from the synthetic GHO fixtures:

    who_atbrth_synthetic_cases.json, atbrth_synthetic_cases.json
    who_dptcov_synthetic_cases.json, dptcov_synthetic_cases.json
    who_physpc_synthetic_cases.json, physpc_synthetic_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_who_cases.py

The fixtures (``tests/fixtures/who/<code>_synthetic.json``) are invented
GHO-shaped responses, not WHO data, because WHO extracts are not
distributed with the repository while redistribution rights are open
(docs/data-governance-review.md, GOV-1). The legacy code does not know the
difference: it runs on them exactly as on a GHO response.

``--real DIR`` runs the same code on the real GHO row subsets kept outside
the repository (``DIR/fixtures/<code>_sample.json``) and writes the
original golden names (``who_atbrth_cases.json``, ``atbrth_cases.json``,
...) to ``DIR/golden``; tests/golden/test_golden_who_real_data.py reads them.
The real golden files of 2026-10-18 are pinned by the checksums in
``tests/fixtures/who/REAL_DATA.sha256``; regenerating them changes their
``generated_at`` stamp, so do it only to replace that evidence deliberately.

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the fixture as the one raw document the legacy
collector stored (the parsed GHO response object; the cleaner reads its
``value`` list); the ``compute_*`` and ``impute_*`` view functions run
unwrapped from their decorators with their collection handles stubbed the
same way. Each indicator is also run once with no rows at all.

Only ATBRTH, DPTCOV and PHYSPC are generated. FAMPLN's compute route stores
no score (its score function names ``UNSDG_FAMPLN`` while the data is
``WHO_FAMPLN``), so there is no executable output to record (FAMPLN-1).
CSTUNT's files come from ``generate_healthcare_cases.py``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import CollectionStub, observation_records, records, unwrap
from generate_legacy_cleaner_cases import CleanStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
INDICATORS = {"ATBRTH": "MDG_0000000025", "DPTCOV": "WHS4_100", "PHYSPC": "HWF_0001"}  # indicator: GHO code
REFERENCE_CLASS = {"ATBRTH": ("CHE", "GBR", "NLD", "BEL", "SWE")}  # impute_reference_class_average calls in impute_atbrth, in order


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "pg", "hlc", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class RawPayloadStub:
    """``sspi_raw_api_data`` for the WHO datasource: the parsed response object as the one raw document."""

    def __init__(self, payload):
        self.payload = payload

    def fetch_raw_data(self, source_info):
        return [{"Raw": json.loads(json.dumps(self.payload))}]


class MetadataStub:
    def get_source_info(self, code):
        return {"OrganizationCode": "WHO"}

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def output_conflicts(observed, imputed):
    observed_ids = {(d["CountryCode"], d["Year"]) for d in observed}
    counts = {}
    for d in imputed:
        counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
    return {
        "observed_and_imputed": [list(i) for i in sorted(observed_ids & set(counts))],
        "duplicate_imputed": [list(i) for i in sorted(i for i, n in counts.items() if n > 1)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", metavar="DIR", help="run on the real GHO subsets in DIR/fixtures and write to DIR/golden")
    args = parser.parse_args()
    if args.real:
        real = os.path.abspath(args.real)
        fixtures = {indicator: os.path.join(real, "fixtures", f"{code}_sample.json") for indicator, code in INDICATORS.items()}
        out_dir, suffix = os.path.join(real, "golden"), ""
    else:
        fixtures = {indicator: f"tests/fixtures/who/{code}_synthetic.json" for indicator, code in INDICATORS.items()}
        out_dir, suffix = HERE, "_synthetic"

    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))
    metadata = MetadataStub()

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
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    def run_routes(module_name, indicator, clean):
        module = importlib.import_module(module_name)
        module.app, module.parse_json = logger, lambda value: value
        module.sspi_metadata, module.sspi_clean_api_data = metadata, CollectionStub(clean)
        module.sspi_indicator_data = CollectionStub()
        if hasattr(module, "sspi_imputed_data"):
            module.sspi_imputed_data = CollectionStub()
        observed = unwrap(getattr(module, f"compute_{indicator.lower()}"))()
        impute = getattr(module, f"impute_{indicator.lower()}", None)
        if impute is None:
            return observed, None, None
        try:
            return observed, unwrap(impute)(), None
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            return observed, None, f"{type(exc).__name__}: {exc}"

    for indicator, gho in INDICATORS.items():
        fixture_path = fixtures[indicator]
        dataset = f"WHO_{indicator}"
        with open(os.path.join(NEW_REPO, fixture_path), encoding="utf-8") as fh:
            payload = json.load(fh)
        cleaner_module = importlib.import_module(f"sspi_flask_app.api.core.datasets.who.who_{indicator.lower()}")
        cleaner_module.sspi_raw_api_data = RawPayloadStub(payload)
        cleaner_module.sspi_clean_api_data, cleaner_module.sspi_metadata = CleanStub(), metadata
        clean = dataset_cleaner_registry[dataset]()
        assert clean and all(d["DatasetCode"] == dataset for d in clean)
        rows = payload["value"]
        observations = observation_records(clean)
        write(
            f"who_{indicator.lower()}{suffix}_cases.json",
            {
                "generated_from": generated_from([f"{cleaner_module.__name__}.clean_who_{indicator.lower()} (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.who.clean_who_data"], fixture_path),
                "dataset_code": dataset,
                "source_indicator": gho,
                "observations": observations,
                "skipped_areas": sorted({(r["SpatialDim"], r["SpatialDimType"]) for r in rows if r["SpatialDimType"] != "COUNTRY"}),
                "no_data_rows": sum(1 for r in rows if r["SpatialDimType"] == "COUNTRY" and r["Value"] == "No data"),
                "descriptions": sorted({d["Description"] for d in clean}),
                "datasources": sorted({str(d["Datasource"]) for d in clean}),
                "legacy_document_keys": sorted({k for d in clean for k in d}),
            },
        )
        years = [o["year"] for o in observations]
        print(f"{dataset}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}")

        module_name = f"sspi_flask_app.api.core.sspi.pg.hlc.{indicator.lower()}"
        observed, imputed, error = run_routes(module_name, indicator, clean)
        assert error is None, error
        front = frontmatter(indicator)
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        (observed_unit,) = {d["Unit"] for d in observed}
        case = {
            "generated_from": generated_from(
                [f"registered @dataset_cleaner function for {dataset} (Mongo handles stubbed)", f"{module_name}.compute_{indicator.lower()} (unwrapped view function, collection handles stubbed)"]
                + ([f"{module_name}.impute_{indicator.lower()} (unwrapped view function, collection handles stubbed)"] if imputed is not None else []),
                fixture_path,
            ),
            "indicator_code": indicator,
            "formula": f"goalpost({dataset}, {lg:g}, {ug:g})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [lg, ug],
            "unit": observed_unit,
            "impute_route_exists": imputed is not None,
            "observed_scores": records(observed, imputation=True),
            "legacy_impute_error": None,
        }
        if imputed is not None:
            case["imputed_unit"] = sorted({d["Unit"] for d in imputed})
            case["series_fill"] = {"forward_to": 2023, "backward_to": 2000, "interpolation": "every interior gap, any year"}
            case["imputed_scores"] = records(imputed, imputation=True)
            case["legacy_output_conflicts"] = output_conflicts(observed, imputed)
        if indicator in REFERENCE_CLASS:
            values = [d["Value"] for d in clean]
            case["reference_class"] = {"recipients": list(REFERENCE_CLASS[indicator]), "years": [2000, 2023], "reference": "every clean row of the dataset, all countries and years", "reference_count": len(values), "mean": sum(values) / len(values)}
        empty_observed, empty_imputed, empty_error = run_routes(module_name, indicator, [])
        case["empty_dataset"] = {"observed_scores": records(empty_observed, imputation=True), "imputed_scores": None if empty_imputed is None else records(empty_imputed, imputation=True), "legacy_impute_error": empty_error}
        write(f"{indicator.lower()}{suffix}_cases.json", case)
        summary = f"{indicator}: {len(observed)} observed (unit {observed_unit!r})"
        if imputed is not None:
            summary += f", {len(imputed)} imputed ({min(d['Year'] for d in imputed)}-{max(d['Year'] for d in imputed)}, units {case['imputed_unit']})"
        if indicator in REFERENCE_CLASS:
            summary += f", reference mean {case['reference_class']['mean']!r} over {case['reference_class']['reference_count']} rows"
        print(summary + f"; empty dataset: {len(empty_observed)} observed, impute route: {empty_error}")
    print(f"from {commit}")


if __name__ == "__main__":
    main()
