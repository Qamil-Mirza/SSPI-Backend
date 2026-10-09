"""Generate the Greenhouse Gases golden files from the committed fixtures:

    unfao_bfprod_cases.json, unfao_bfcons_cases.json, wb_populn_cases.json,
    iea_tco2em_cases.json                     (the new source datasets)
    beefmk_cases.json, coalpw_cases.json, gtrans_cases.json
                                              (both legacy routes each)

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \
        /path/to/sspi-backend/tests/golden/generate_ghg_cases.py

Everything recorded is the legacy code's own output. The registered
``@dataset_cleaner`` functions run with their Mongo handles replaced by
in-memory stubs serving the committed rows; the ``compute_*`` and
``impute_*`` view functions of ``api/core/sspi/sus/ghg`` run unwrapped from
their decorators with their collection handles stubbed by
:class:`Collection`, which answers the queries those routes make (equality,
``$in``, ``$or``, ``$gte``/``$lte``) and returns documents in insertion
order, as MongoDB does. The input-level impute routes' own
``score_indicator`` call is observed to record the country-years it left
incomplete, which the routes compute and discard.

Fixtures:

* ``tests/fixtures/iea/TESbySource_sample.json``: the ALTNRG fixture,
  unchanged; COALPW reads the same seven datasets;
* ``tests/fixtures/iea/CO2BySector_sample.json``: ``IEA_TCO2EM``;
* ``tests/fixtures/wb/SP.POP.TOTL_sample.json``: ``WB_POPULN``;
* ``tests/fixtures/fao/FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv``:
  ``UNFAO_BFPROD`` and ``UNFAO_BFCONS``. The legacy collector read the
  FAOSTAT JSON API (now behind authentication); :func:`as_legacy_api_rows`
  presents each bulk row the way that API did, as
  ``generate_fao_land_cases.py`` does for the land datasets: ISO3 where the
  area's M49 code is a country, the FAO area code otherwise (which the
  legacy ``^[A-Z]{3}$`` filter drops), the bulk file's strings for year and
  value. The legacy API was asked for element 2510 (Production); the bulk
  file's code for it is 5511.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_fao_land_cases import conflicts, identities, records
from generate_iea_cases import incomplete_records
from generate_inequality_cases import observation_records, unwrap
from generate_legacy_cleaner_cases import CleanStub, RawStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
TES_FIXTURE = "tests/fixtures/iea/TESbySource_sample.json"
CO2_FIXTURE = "tests/fixtures/iea/CO2BySector_sample.json"
WB_FIXTURE = "tests/fixtures/wb/SP.POP.TOTL_sample.json"
FBS_FIXTURE = "tests/fixtures/fao/FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv"
TES_DATASETS = ("IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL")
# dataset -> (bulk element code, item code, the element the legacy API was asked for)
FBS_SERIES = {"UNFAO_BFPROD": ("5511", "2731", "2510"), "UNFAO_BFCONS": ("645", "2731", "645")}


def frontmatter(code):
    import yaml

    with open(os.path.join(OLD_REPO, "methodology", "sus", "ghg", code.lower(), "methodology.md")) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    def __init__(self, groups):
        self.groups = groups

    def get_source_info(self, code):
        return {"OrganizationCode": code.split("_")[0]}

    def record_dataset_range(self, documents, code):
        return None

    def country_group(self, name):
        return list(self.groups[name])

    def get_goalposts(self, code):
        front = frontmatter(code)
        return front["LowerGoalpost"], front["UpperGoalpost"]


def matches(document, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(matches(document, q) for q in wanted):
                return False
            continue
        value = document.get(key)
        if isinstance(wanted, dict):
            for operator, operand in wanted.items():
                if operator == "$in":
                    ok = value in operand
                elif operator == "$gte":
                    ok = value is not None and value >= operand
                elif operator == "$lte":
                    ok = value is not None and value <= operand
                else:
                    raise AssertionError(f"query operator {operator} not stubbed")
                if not ok:
                    return False
        elif value != wanted:
            return False
    return True


class Collection:
    """An in-memory collection answering the queries the three routes make."""

    def __init__(self, documents=()):
        self.documents = json.loads(json.dumps(list(documents)))

    def find(self, query):
        return [json.loads(json.dumps(d)) for d in self.documents if matches(d, query)]  # fresh copies, as Mongo would return

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [d for d in self.documents if not matches(d, query)]
        return before - len(self.documents)

    def insert_many(self, documents):
        self.documents.extend(json.loads(json.dumps(documents)))
        return len(documents)


def as_legacy_api_rows(bulk_rows, element, item):
    from pycountry import countries

    out = []
    for row in bulk_rows:
        if row["Element Code"] != element or row["Item Code"] != item:
            continue
        m49 = row["Area Code (M49)"].lstrip("'")
        country = countries.get(numeric=f"{int(m49):03d}")
        out.append(
            {
                "Area Code (ISO3)": country.alpha_3 if country is not None else row["Area Code"],
                "Area": row["Area"],
                "Item Code": row["Item Code"],
                "Item": row["Item"],
                "Element": row["Element"],
                "Year": row["Year"],
                "Value": row["Value"],
                "Unit": row["Unit"],
                "Flag": row["Flag"],
            }
        )
    return out


def main() -> None:
    import pycountry
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    with open(os.path.join(OLD_REPO, "local", "country-groups.json")) as fh:
        metadata = MetadataStub(json.load(fh))
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))

    def generated_from(functions, fixtures):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixtures": list(fixtures),
        }

    def write(name, payload):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)

    def clean(dataset, module_path, raw_rows):
        module = importlib.import_module(module_path)
        module.sspi_raw_api_data, module.sspi_clean_api_data, module.sspi_metadata = RawStub(raw_rows), CleanStub(), metadata
        cleaned = dataset_cleaner_registry[dataset]()
        assert cleaned and all(d["DatasetCode"] == dataset for d in cleaned), dataset
        return module, cleaned

    def describe(dataset, cleaned):
        years = [d["Year"] for d in cleaned]
        print(f"{dataset}: {len(cleaned)} observations, {len({d['CountryCode'] for d in cleaned})} countries, {min(years)}-{max(years)}, units {sorted({d['Unit'] for d in cleaned})}")

    # ------------------------------------------------------------------ source datasets
    with open(os.path.join(NEW_REPO, FBS_FIXTURE), encoding="utf-8", newline="") as fh:
        bulk_rows = list(csv.DictReader(fh))
    fbs_clean = {}
    for dataset, (element, item, api_element) in FBS_SERIES.items():
        api_rows = as_legacy_api_rows(bulk_rows, element, item)
        module, cleaned = clean(dataset, f"sspi_flask_app.api.core.datasets.unfao.{dataset.lower()}", [{"data": api_rows}])
        fbs_clean[dataset] = cleaned
        skipped = sorted({(r["Area Code (ISO3)"], r["Area"]) for r in api_rows if len(r["Area Code (ISO3)"]) != 3 or any(ch.isdigit() for ch in r["Area Code (ISO3)"])})
        write(
            f"{dataset.lower()}_cases.json",
            {
                "generated_from": generated_from([f"{module.__name__}.{dataset_cleaner_registry[dataset].__name__} (registered @dataset_cleaner, Mongo handles stubbed)"], [FBS_FIXTURE]),
                "dataset_code": dataset,
                "source_filters": {"domain": "FBS", "element_code": element, "item_code": item},
                "legacy_api_element": api_element,
                "source_elements": sorted({r["Element"] for r in api_rows}),
                "source_units": sorted({r["Unit"] for r in api_rows}),
                "observations": observation_records(cleaned),
                "skipped_areas": [list(s) for s in skipped],
                "empty_source_values": sum(1 for r in api_rows if r["Value"] == ""),
                "zero_source_values": sum(1 for r in api_rows if r["Value"] != "" and float(r["Value"]) == 0),
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
            },
        )
        describe(dataset, cleaned)

    with open(os.path.join(NEW_REPO, WB_FIXTURE)) as fh:
        _, wb_rows = json.load(fh)
    module, populn_clean = clean("WB_POPULN", "sspi_flask_app.api.core.datasets.wb.wb_populn", wb_rows)
    skipped, missing = {}, 0
    for row in wb_rows:
        code = row["countryiso3code"] or row["country"]["id"]
        if pycountry.countries.get(alpha_3=code) is None:
            skipped[(code, row["country"]["value"])] = None
        elif not row["value"]:
            missing += 1
    write(
        "wb_populn_cases.json",
        {
            "generated_from": generated_from([f"{module.__name__}.clean_wb_populn (registered @dataset_cleaner, Mongo handles stubbed)", "sspi_flask_app.api.datasource.worldbank.clean_wb_data"], [WB_FIXTURE]),
            "dataset_code": "WB_POPULN",
            "source_indicator": "SP.POP.TOTL",
            "observations": observation_records(populn_clean),
            "descriptions": sorted({d["Description"] for d in populn_clean}),
            "skipped_areas": [list(s) for s in sorted(skipped)],
            "empty_source_values": missing,
            "legacy_document_keys": sorted({k for d in populn_clean for k in d}),
        },
    )
    describe("WB_POPULN", populn_clean)

    with open(os.path.join(NEW_REPO, CO2_FIXTURE), encoding="utf-8") as fh:
        co2_rows = json.load(fh)
    module, tco2em_clean = clean("IEA_TCO2EM", "sspi_flask_app.api.core.datasets.iea.iea_tco2em", co2_rows)
    transport = [r for r in co2_rows if r["seriesLabel"] == "Transport Sector"]
    mapped = [r for r in transport if pycountry.countries.get(alpha_3=r["country"])]
    write(
        "iea_tco2em_cases.json",
        {
            "generated_from": generated_from([f"{module.__name__}.clean_iea_tco2em (registered @dataset_cleaner, Mongo handles stubbed)"], [CO2_FIXTURE]),
            "dataset_code": "IEA_TCO2EM",
            "source_request": {"url": "https://api.iea.org/stats/indicator/CO2BySector", "indicator": "CO2BySector"},
            "dimensions": {"seriesLabel": "Transport Sector"},
            "source_units": sorted({r["units"] for r in transport}),
            "source_flows": sorted({r["flow"] for r in transport}),
            "observations": observation_records(tco2em_clean),
            "skipped_areas": sorted({r["country"] for r in transport} - {r["country"] for r in mapped}),
            "empty_source_values": sum(1 for r in mapped if r["value"] is None),
            "zero_source_values": sum(1 for r in mapped if r["value"] is not None and not r["value"]),
            "legacy_document_keys": sorted({k for d in tco2em_clean for k in d}),
        },
    )
    describe("IEA_TCO2EM", tco2em_clean)

    with open(os.path.join(NEW_REPO, TES_FIXTURE), encoding="utf-8") as fh:
        tes_rows = json.load(fh)
    tes_clean = []
    for dataset in TES_DATASETS:
        _, cleaned = clean(dataset, f"sspi_flask_app.api.core.datasets.iea.{dataset.lower()}", tes_rows)
        tes_clean.extend(cleaned)

    # ------------------------------------------------------------------ routes
    def route_module(code, clean_documents):
        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.sus.ghg.{code.lower()}")
        module.app, module.parse_json = logger, (lambda value: value)
        module.sspi_metadata, module.sspi_clean_api_data = metadata, Collection(clean_documents)
        module.sspi_indicator_data, module.sspi_incomplete_indicator_data, module.sspi_imputed_data = Collection(), Collection(), Collection()
        return module

    def run_routes(code, clean_documents, *, record_impute_incomplete):
        module = route_module(code, clean_documents)
        observed = unwrap(getattr(module, f"compute_{code.lower()}"))()
        observed_incomplete = module.sspi_incomplete_indicator_data.find({})
        left = []
        if record_impute_incomplete:
            legacy_score_indicator = module.score_indicator

            def recording_score_indicator(*args, **kwargs):
                complete, incomplete = legacy_score_indicator(*args, **kwargs)
                left.extend(json.loads(json.dumps(incomplete)))
                return complete, incomplete

            module.score_indicator = recording_score_indicator
        try:
            imputed = unwrap(getattr(module, f"impute_{code.lower()}"))()
        finally:
            if record_impute_incomplete:
                module.score_indicator = legacy_score_indicator
        (unit,) = {d["Unit"] for d in observed + imputed}
        methods = {}
        for d in imputed:
            for method in {d.get("ImputationMethod")} | {x.get("ImputationMethod") for x in d.get("Datasets", []) if x.get("Imputed")}:
                if method:
                    methods[method] = methods.get(method, 0) + 1
        print(f"{code}: {len(observed)} observed, {len(observed_incomplete)} incomplete; {len(imputed)} imputed {methods}; unit {unit!r}; conflicts {conflicts(observed, imputed)}")
        return module, observed, observed_incomplete, imputed, left, unit

    def facts(code):
        front = frontmatter(code)
        return {
            "indicator_code": code,
            "dataset_codes": list(front["DatasetCodes"]),
            "methodology_score_function": front["ScoreFunction"].strip(),
            "methodology_description": front["Description"],
            "goalposts": [front["LowerGoalpost"], front["UpperGoalpost"]],
        }

    def functions(module, code):
        return [
            "registered @dataset_cleaner functions for the input datasets (Mongo handles stubbed)",
            f"{module.__name__}.compute_{code.lower()} (unwrapped view function, collection handles stubbed)",
            f"{module.__name__}.impute_{code.lower()} (unwrapped view function, collection handles stubbed)",
        ]

    # COALPW: the ALTNRG datasets, ALTNRG's impute shape, its own formula
    module, observed, observed_incomplete, imputed, left, unit = run_routes("COALPW", tes_clean, record_impute_incomplete=True)
    write(
        "coalpw_cases.json",
        {
            "generated_from": generated_from(functions(module, "COALPW"), [TES_FIXTURE]),
            **facts("COALPW"),
            "unit": unit,
            "impute_route_exists": True,
            "imputation": {"zero_fill": {"recipient_group": "SSPI67", "recipients": "members with no row in the dataset", "years": [2000, 2023], "unit": "PJ"}, "backward_to": 2000, "forward_to": 2023, "interpolation": "every interior gap, any year", "zero_total_score": 1.0},
            "observed_scores": records(observed),
            "observed_incomplete": incomplete_records(observed_incomplete),
            "imputed_scores": records(imputed),
            "incomplete_after_imputation": incomplete_records(left),
            "legacy_impute_error": None,
            "legacy_output_conflicts": conflicts(observed, imputed),
        },
    )

    # GTRANS: transport CO2 per person, forward extrapolation of the CO2 input only
    module, observed, observed_incomplete, imputed, left, unit = run_routes("GTRANS", tco2em_clean + populn_clean, record_impute_incomplete=True)
    write(
        "gtrans_cases.json",
        {
            "generated_from": generated_from(functions(module, "GTRANS"), [CO2_FIXTURE, WB_FIXTURE]),
            **facts("GTRANS"),
            "unit": unit,
            "impute_route_exists": True,
            "imputation": {"window": [2000, 2023], "forward_to": 2023, "datasets_carried_forward": ["IEA_TCO2EM"], "backward": None, "interpolation": None, "reference_class": None},
            "observed_scores": records(observed),
            "observed_incomplete": incomplete_records(observed_incomplete),
            "imputed_scores": records(imputed),
            "incomplete_after_imputation": incomplete_records(left),
            "legacy_impute_error": None,
            "legacy_output_conflicts": conflicts(observed, imputed),
        },
    )

    # BEEFMK: score-level extrapolation and a hard-coded reference-class recipient
    beefmk_clean = fbs_clean["UNFAO_BFPROD"] + fbs_clean["UNFAO_BFCONS"] + populn_clean
    module, observed, observed_incomplete, imputed, _, unit = run_routes("BEEFMK", beefmk_clean, record_impute_incomplete=False)
    write(
        "beefmk_cases.json",
        {
            "generated_from": generated_from(functions(module, "BEEFMK"), [FBS_FIXTURE, WB_FIXTURE]),
            **facts("BEEFMK"),
            "route_goalposts": {"production_per_capita": [50, 0], "consumption": [50, 0]},
            "unit": unit,
            "impute_route_exists": True,
            "score_extrapolation": {"backward_to": 2000, "forward_to": 2023, "reference_class": {"listed_recipients": ["SGP"], "years": [2000, 2023]}},
            "observed_scores": records(observed),
            "observed_incomplete_identities": identities(observed_incomplete),
            "imputed_scores": records(imputed),
            "legacy_impute_error": None,
            "legacy_output_conflicts": conflicts(observed, imputed),
        },
    )
    print(f"from {commit}")


if __name__ == "__main__":
    main()
