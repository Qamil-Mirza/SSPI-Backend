"""Generate the Financial Sector golden files from the committed source fixtures:

    wb_credit_cases.json, wb_dposit_cases.json, fdepth_cases.json
    wb_pubacc_cases.json, pubacc_cases.json

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_financial_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed World Bank samples (one raw document
per API row); the ``compute_fdepth``, ``impute_fdepth`` and
``compute_pubacc`` view functions run unwrapped from their decorators with
their collection handles replaced by :class:`MongoStub`, which answers the
query operators those routes use (equality, ``$in``, ``$gte``) with
MongoDB's semantics, a document without the queried field included: it
matches no equality, ``$in`` or ``$gte`` condition.

The score functions are closures inside the compute routes. They are
observed, not copied: ``score_indicator`` is wrapped to record the function
each route passes, and that legacy function is then evaluated on a few
input combinations the fixtures do not hold (goalpost boundaries, values
beyond them), recording its result.

FDEPTH's impute route is run three times and what it does is recorded: the
queries it makes and how many documents each returns, what it hands
``impute_reference_class_average`` and the exception that ends it.

* on the collections the cleaners and the compute route leave behind (the
  real state of a legacy database after ``clean`` and ``compute``);
* on empty collections;
* on a PROBE: the same collections plus synthetic clean documents written in
  the legacy schema of before July 2025 (``IndicatorCode`` FDEPTH,
  ``DatasetCode`` CREDIT / DPOSIT), the schema the route's query and slices
  were written for. Nothing in the pinned code writes such documents; the
  probe only shows that the route still fails when its query does match:
  ``slice_dataset`` reads a ``Datasets`` list that clean documents never
  have, so the reference class is still empty.

FSTABL has no executable route at the pinned commit; this script checks that
fact (no compute or impute view, no IMF_FSTABL cleaner) and writes nothing
for it.
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
    "WB_CREDIT": ("FS.AST.PRVT.GD.ZS", "tests/fixtures/wb/FS.AST.PRVT.GD.ZS_sample.json"),
    "WB_DPOSIT": ("GFDD.OI.02", "tests/fixtures/wb/GFDD.OI.02_sample.json"),
    "WB_PUBACC": ("FX.OWN.TOTL.ZS", "tests/fixtures/wb/FX.OWN.TOTL.ZS_sample.json"),
}
# (WB_CREDIT, WB_DPOSIT) handed to the legacy FDEPTH closure
FDEPTH_SCORE_FUNCTION_CASES = (
    ("both at the lower goalposts", 0.0, 0.0),
    ("both at the upper goalposts", 200.0, 100.0),
    ("both at half way", 100.0, 50.0),
    ("credit beyond its upper goalpost", 250.0, 50.0),
    ("deposits beyond their upper goalpost", 100.0, 150.0),
    ("deposits at the credit goalpost", 100.0, 200.0),
    ("fractional values", 117.099430029325, 122.5862),
)
# WB_PUBACC handed to the legacy PUBACC closure
PUBACC_SCORE_FUNCTION_CASES = (
    ("lower goalpost", 0.0),
    ("upper goalpost", 100.0),
    ("integer upper goalpost", 100),
    ("half way", 50.0),
    ("fractional value", 88.6918012421116),
)


def frontmatter(indicator):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "ms", "fin", indicator.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"DatasetCode": code}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def main() -> None:
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.core.sspi import compute_bp, impute_bp  # noqa: F401 - imported for the route check below
    from sspi_flask_app.api.resources import utilities

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        groups = json.load(fh)
    metadata = MetadataStub(groups)
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixtures):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            **({"fixture": fixtures[0]} if len(fixtures) == 1 else {"fixtures": list(fixtures)}),
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    # ------------------------------------------------------------ FSTABL: nothing executable
    fstabl = importlib.import_module("sspi_flask_app.api.core.sspi.ms.fin.fstabl")
    assert not [name for name in vars(fstabl) if name.endswith("fstabl")], "FSTABL now defines a view function"
    assert "IMF_FSTABL" not in dataset_cleaner_registry and "WB_FSTABL" in dataset_cleaner_registry
    print("FSTABL: no compute or impute view; IMF_FSTABL has no cleaner; WB_FSTABL has one (not read by any route)")

    # ------------------------------------------------------------ the three World Bank datasets
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
                "generated_from": generated_from([f"{module.__name__}.{dataset_cleaner_registry[code].__name__} (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], [fixture]),
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
        print(f"{code}: {len(observations)} observations, {len({o['country_code'] for o in observations})} countries, {min(years)}-{max(years)}, {len(skipped)} skipped areas, {without_code} rows without a code, {missing} missing values")

    captured, outcomes = {}, {}
    original_score_indicator = utilities.score_indicator

    def capturing_score_indicator(documents, indicator_code, score_function, unit, *args, **kwargs):
        captured.setdefault(indicator_code, score_function)  # the compute route's closure: its first call
        outcomes[indicator_code] = original_score_indicator(documents, indicator_code, score_function, unit, *args, **kwargs)
        return outcomes[indicator_code]

    # ------------------------------------------------------------------- FDEPTH
    module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.fin.fdepth")
    module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata
    module.score_indicator = capturing_score_indicator
    reference_calls = []
    original_reference = module.impute_reference_class_average

    def reference_class(country_code, start_year, end_year, item_type, item_code, ref_data):
        reference_calls.append({"country_code": country_code, "years": [start_year, end_year], "item_type": item_type, "item_code": item_code, "reference_documents": len(ref_data)})
        return original_reference(country_code, start_year, end_year, item_type, item_code, ref_data)

    module.impute_reference_class_average = reference_class

    def fdepth_state(clean_documents):
        log = []
        return {
            "log": log,
            "clean": MongoStub("sspi_clean_api_data", clean_documents, log),
            "indicator": MongoStub("sspi_indicator_data", (), log),
            "incomplete": MongoStub("sspi_incomplete_indicator_data", (), log),
            # a stale imputed score from an earlier run: shows what the route's first statement does to it
            "imputed": MongoStub("sspi_imputed_data", [{"IndicatorCode": "FDEPTH", "CountryCode": "ZZZ", "Year": 1999, "Score": 0.5, "Unit": "Index", "StaleMarker": True}], log),
        }

    def bind(state):
        module.sspi_clean_api_data, module.sspi_indicator_data = state["clean"], state["indicator"]
        module.sspi_incomplete_indicator_data, module.sspi_imputed_data = state["incomplete"], state["imputed"]

    def run_impute(state):
        bind(state)
        state["log"].clear()
        reference_calls.clear()
        try:
            result, error = unwrap(module.impute_fdepth)(), None
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            result, error = None, f"{type(exc).__name__}: {exc}"
        return {
            "legacy_impute_error": error,
            "returned": result,
            "queries": list(state["log"]),
            "reference_class_calls": list(reference_calls),
            "imputed_collection_after": state["imputed"].documents,
        }

    state = fdepth_state(clean["WB_CREDIT"] + clean["WB_DPOSIT"])
    bind(state)
    observed = unwrap(module.compute_fdepth)()
    incomplete = list(state["incomplete"].documents)
    assert len(state["indicator"].documents) == len(observed)
    fixture_impute = run_impute(state)

    empty_state = fdepth_state([])
    bind(empty_state)
    empty_observed = unwrap(module.compute_fdepth)()
    empty_impute = run_impute(empty_state)

    sspi67 = set(groups["SSPI67"])
    probe_documents = [
        {"IndicatorCode": "FDEPTH", "DatasetCode": code.removeprefix("WB_"), "CountryCode": d["CountryCode"], "Year": d["Year"], "Value": d["Value"], "Unit": d["Unit"], "Probe": "synthetic legacy-schema document"}
        for code in ("WB_CREDIT", "WB_DPOSIT")
        for d in clean[code]
        if d["CountryCode"] in sspi67 and d["Year"] >= 2000
    ]
    probe_state = fdepth_state(clean["WB_CREDIT"] + clean["WB_DPOSIT"] + probe_documents)
    bind(probe_state)
    unwrap(module.compute_fdepth)()
    probe_impute = run_impute(probe_state)
    assert probe_impute["queries"][1]["returned"] == len(probe_documents), probe_impute["queries"]

    front = frontmatter("FDEPTH")
    score_fdepth = captured["FDEPTH"]
    assert list(score_fdepth.__code__.co_varnames[: score_fdepth.__code__.co_argcount]) == ["WB_CREDIT", "WB_DPOSIT"]
    (observed_unit,) = {d["Unit"] for d in observed}
    fixtures = [FIXTURES["WB_CREDIT"][1], FIXTURES["WB_DPOSIT"][1]]
    write(
        "fdepth_cases.json",
        {
            "generated_from": generated_from(
                [
                    "registered @dataset_cleaner functions for WB_CREDIT and WB_DPOSIT (Mongo handles stubbed)",
                    f"{module.__name__}.compute_fdepth (unwrapped view function, collection handles stubbed)",
                    f"{module.__name__}.impute_fdepth (unwrapped view function, collection handles stubbed; run on three states, see impute_route)",
                ],
                fixtures,
            ),
            "indicator_code": "FDEPTH",
            "formula": "goalpost(WB_CREDIT, 0, 200) / 2 + goalpost(WB_DPOSIT, 0, 100) / 2",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "metadata_goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
            "input_goalposts": {"WB_CREDIT": [0, 200], "WB_DPOSIT": [0, 100]},
            "score_function_parameters": ["WB_CREDIT", "WB_DPOSIT"],
            "unit": observed_unit,
            "impute_route_exists": True,
            "observed_scores": records(observed, imputation=False),
            "incomplete_identities": identities(incomplete),
            "incomplete_groups": sorted(([d["CountryCode"], d["Year"], sorted(x["DatasetCode"] for x in d["Datasets"])] for d in incomplete), key=lambda r: (r[0], r[1])),
            "imputed_scores": [],
            "legacy_impute_error": fixture_impute["legacy_impute_error"],
            "impute_route": {
                "fixture": {k: v for k, v in fixture_impute.items() if k != "returned"},
                "empty_dataset": {k: v for k, v in empty_impute.items() if k != "returned"},
                "legacy_schema_probe": {"synthetic_documents_added": len(probe_documents), **{k: v for k, v in probe_impute.items() if k != "returned"}},
            },
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=False), "legacy_impute_error": empty_impute["legacy_impute_error"]},
            "score_function_cases": [{"case": name, "inputs": {"WB_CREDIT": credit, "WB_DPOSIT": deposit}, "score": score_fdepth(credit, deposit)} for name, credit, deposit in FDEPTH_SCORE_FUNCTION_CASES],
        },
    )
    years = [d["Year"] for d in observed]
    print(
        f"FDEPTH: {len(observed)} observed ({min(years)}-{max(years)}, unit {observed_unit!r}), {len(incomplete)} incomplete; "
        f"impute route: fixture -> {fixture_impute['legacy_impute_error']}, empty -> {empty_impute['legacy_impute_error']}, "
        f"probe ({len(probe_documents)} legacy-schema documents) -> {probe_impute['legacy_impute_error']}"
    )

    # ------------------------------------------------------------------- PUBACC
    module = importlib.import_module("sspi_flask_app.api.core.sspi.ms.fin.pubacc")
    module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata
    module.score_indicator = capturing_score_indicator
    clean_collection, indicator_data = MongoStub("sspi_clean_api_data", clean["WB_PUBACC"]), MongoStub("sspi_indicator_data")
    module.sspi_clean_api_data, module.sspi_indicator_data = clean_collection, indicator_data
    observed = unwrap(module.compute_pubacc)()
    _, incomplete = outcomes["PUBACC"]
    module.sspi_clean_api_data, module.sspi_indicator_data = MongoStub("sspi_clean_api_data"), MongoStub("sspi_indicator_data")
    empty_observed = unwrap(module.compute_pubacc)()
    front = frontmatter("PUBACC")
    score_pubacc = captured["PUBACC"]
    (observed_unit,) = {d["Unit"] for d in observed}
    write(
        "pubacc_cases.json",
        {
            "generated_from": generated_from(
                ["registered @dataset_cleaner function for WB_PUBACC (Mongo handles stubbed)", f"{module.__name__}.compute_pubacc (unwrapped view function, collection handles stubbed)"],
                [FIXTURES["WB_PUBACC"][1]],
            ),
            "indicator_code": "PUBACC",
            "formula": f"goalpost(WB_PUBACC, {front['LowerGoalpost']}, {front['UpperGoalpost']})",
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
            "unit": observed_unit,
            "impute_route_exists": hasattr(module, "impute_pubacc"),
            "scores": records(observed, imputation=False),
            "incomplete_identities": identities(incomplete),  # the route discarded them; recorded from score_indicator's result
            "empty_dataset": {"observed_scores": records(empty_observed, imputation=False)},
            "score_function_cases": [{"case": name, "inputs": {"WB_PUBACC": value}, "score": score_pubacc(value)} for name, value in PUBACC_SCORE_FUNCTION_CASES],
        },
    )
    years = sorted({d["Year"] for d in observed})
    print(f"PUBACC: {len(observed)} scores, years {years}, unit {observed_unit!r}")


if __name__ == "__main__":
    main()
