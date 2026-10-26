"""Generate the Rights golden files with the pinned legacy code:

    vdem_rulelw_synthetic_cases.json, rulelw_synthetic_cases.json
    vdem_edemoc_synthetic_cases.json, edemoc_synthetic_cases.json
        from the committed synthetic archive tests/fixtures/vdem/V-Dem-CY-FullOthers_csv_v13_synthetic.zip

Run inside the old repository's virtualenv:

    cd ../sspi-data-webapp
    PYTHONPATH=/path/to/sspi-backend/tests/golden env/bin/python \\
        /path/to/sspi-backend/tests/golden/generate_rights_cases.py [--real DIR]

``--real DIR`` reads the original archive kept outside the repository
(``DIR/vdem/V-Dem-CY-FullOthers_csv_v13.zip``; docs/data-governance-review.md,
GOV-6) instead of the synthetic one, and writes ``vdem_rulelw_cases.json``,
``rulelw_cases.json``, ``vdem_edemoc_cases.json`` and ``edemoc_cases.json``
to ``DIR/vdem/golden/``, never to the repository.

Everything recorded is the legacy code's own output:

* collection: ``collect_iterator`` of ``api/core/dataset.py`` (what the
  collect route runs) for both datasets, with ``requests.get`` answering
  with the archive's bytes and ``sspi_raw_api_data`` the legacy
  ``SSPIRawAPIData`` class itself over an in-memory collection, so its
  validation, its fragmentation of large CSV text and its reassembly in
  ``fetch_raw_data`` all run;
* cleaning: the registered ``@dataset_cleaner`` functions, with the
  module's ``datetime`` replaced by one whose ``now()`` is a fixed date
  (the cleaners' upper year bound is the calendar year of the run). The
  golden date is :data:`EVALUATION_DATE`; the synthetic files also record
  the cleaner at :data:`EARLIER_EVALUATION_DATE`. The clean inserts are
  checked by the legacy clean collection's ``validate_documents_format``;
* scoring: ``compute_rulelw``/``impute_rulelw`` and
  ``compute_edemoc``/``impute_edemoc`` unwrapped, with their collection
  handles replaced by ``MongoStub`` collections whose inserts first apply the
  legacy collections' own validation. The impute routes clear
  ``sspi_imputed_data`` and insert into ``sspi_indicator_data``: what each
  collection holds is recorded after compute then impute, after a second
  impute, after a second compute, and after impute then compute.

The score functions are lambdas inside the routes. ``score_indicator`` is
wrapped to observe them, and each is evaluated on inputs no fixture holds.

Invalid variants of the synthetic archive (see its ``build_synthetic.py``)
are also run through the legacy collector and cleaners, recording how
legacy failed.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import io
import itertools
import json
import os
import subprocess
import types
from datetime import datetime, timezone

from generate_inequality_cases import identities, observation_records, records, unwrap
from generate_public_safety_cases import builder, failure, validating
from legacy_stubs import MongoStub

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD_REPO = os.path.abspath(os.path.join(NEW_REPO, "..", "sspi-data-webapp"))
SYNTHETIC = "tests/fixtures/vdem/V-Dem-CY-FullOthers_csv_v13_synthetic.zip"
REAL = "vdem/V-Dem-CY-FullOthers_csv_v13.zip"
URL = "https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip"  # the legacy collector's literal
EVALUATION_DATE = datetime(2026, 10, 26, 12, 0, 0)
EARLIER_EVALUATION_DATE = datetime(2024, 6, 30, 12, 0, 0)
DATASETS = {"RULELW": ("VDEM_RULELW", "v2x_rule"), "EDEMOC": ("VDEM_EDEMOC", "v2x_polyarchy")}
SCORE_FUNCTION_CASES = (("lower goalpost", 0.0), ("upper goalpost", 1.0), ("integer upper goalpost", 1), ("half way", 0.5), ("below the lower goalpost", -0.05), ("beyond the upper goalpost", 1.2), ("fractional value", 0.9876543211))


def frontmatter(path):
    import yaml

    with open(os.path.join(OLD_REPO, path)) as fh:
        return yaml.safe_load(fh.read().split("---")[1])


class MetadataStub:
    """``sspi_metadata`` as the routes and cleaners use it: each dataset's documented ``Source`` block,
    each indicator's documented goalposts."""

    def get_source_info(self, code):
        return frontmatter(f"datasets/vdem/{code.lower()}/documentation.md")["Source"]

    def record_dataset_range(self, documents, code):
        return None

    def get_goalposts(self, code):
        front = frontmatter(f"methodology/pg/rts/{code.lower()}/methodology.md")
        return front["LowerGoalpost"], front["UpperGoalpost"]


def _get(document, dotted):
    for part in dotted.split("."):
        if not isinstance(document, dict) or part not in document:
            return None
        document = document[part]
    return document


class MemoryCollection:
    """The pymongo calls ``SSPIRawAPIData`` makes, over a list: ``insert_one`` sets ``_id`` on the
    caller's dict as pymongo does, ``find`` matches dotted equality queries and applies ``{"_id": 0}``."""

    name = "sspi_raw_api_data"

    def __init__(self):
        self.documents, self.ids = [], itertools.count(1)

    def insert_one(self, document):
        document["_id"] = next(self.ids)
        self.documents.append(copy.deepcopy(document))

    def _matching(self, query):
        return [d for d in self.documents if all(_get(d, k) == v for k, v in query.items())]

    def find(self, query, options=None):
        return [{k: v for k, v in d.items() if k != "_id"} for d in self._matching(query)]

    def find_one(self, query, options=None):
        found = self.find(query, options)
        return found[0] if found else None

    def delete_many(self, query):
        matching = self._matching(query)
        self.documents = [d for d in self.documents if d not in matching]
        return types.SimpleNamespace(deleted_count=len(matching))

    def count_documents(self, query):
        return len(self._matching(query))


def fixed_datetime(moment):
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    return Fixed


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", metavar="DIR", help="read the original archive from DIR and write the golden files there")
    args = parser.parse_args(argv)

    import pandas as pd
    from sspi_flask_app.api.core import dataset as dataset_routes
    from sspi_flask_app.api.core.datasets import dataset_cleaner_registry
    from sspi_flask_app.api.datasource import vdem as vdem_source
    from sspi_flask_app.api.resources import utilities
    from sspi_flask_app.models.database import (
        sspi_clean_api_data,
        sspi_imputed_data,
        sspi_indicator_data,
    )
    from sspi_flask_app.models.database.sspi_raw_api_data import SSPIRawAPIData

    commit = subprocess.check_output(["git", "-C", OLD_REPO, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", OLD_REPO, "status", "--porcelain"], text=True).strip())
    metadata = MetadataStub()
    logger = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a, **k: None))
    cleaner_modules = {code: importlib.import_module(f"sspi_flask_app.api.core.datasets.vdem.{code.lower()}") for code, _ in DATASETS.values()}

    def generated_from(functions, fixture):
        return {
            "repository": "sspi-data-webapp",
            "commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_functions": functions,
            "fixture": fixture,
        }

    def write(directory, name, payload):
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, name), "w") as fh:
            json.dump(payload, fh, indent=1, allow_nan=False)
            fh.write("\n")

    # ----------------------------------------------------------------- collect and clean
    requested = []

    def collect(content):
        """The collect route's iterator for both datasets; returns the legacy raw collection it filled."""
        raw = SSPIRawAPIData(MemoryCollection())

        def get(url, *a, **k):
            requested.append(url)
            return types.SimpleNamespace(status_code=200, content=content)

        vdem_source.requests = types.SimpleNamespace(get=get)
        vdem_source.sspi_raw_api_data = raw
        dataset_routes.sspi_raw_api_data, dataset_routes.sspi_metadata, utilities.sspi_metadata = raw, metadata, metadata
        messages = list(dataset_routes.collect_iterator(["VDEM_RULELW", "VDEM_EDEMOC"], username="generator"))
        return raw, messages

    def clean(raw, code, moment):
        module = cleaner_modules[code]
        module.sspi_raw_api_data, module.sspi_metadata = raw, metadata
        module.sspi_clean_api_data = validating("sspi_clean_api_data", sspi_clean_api_data)
        module.datetime = fixed_datetime(moment)
        return dataset_cleaner_registry[code]()

    def run_variant(content):
        try:
            raw, _ = collect(content)
        except Exception as exc:  # noqa: BLE001 - the legacy behavior is what is recorded
            return {code: f"{type(exc).__name__}: {exc}" for code, _ in DATASETS.values()}
        return {code: failure(lambda code=code: clean(raw, code, EVALUATION_DATE)) for code, _ in DATASETS.values()}

    if args.real:
        with open(os.path.join(args.real, REAL), "rb") as fh:
            content = fh.read()
        fixture, out, suffix, variants = REAL, os.path.join(args.real, "vdem", "golden"), "", {}
    else:
        synthetic = builder("vdem")
        with open(os.path.join(NEW_REPO, SYNTHETIC), "rb") as fh:
            content = fh.read()
        assert synthetic.members(content) == synthetic.members(synthetic.build()), "committed archive differs from build_synthetic.py"
        fixture, out, suffix = SYNTHETIC, HERE, "_synthetic"
        variants = {name: run_variant(synthetic.build(name)) for name in synthetic.VARIANTS}
        requested.clear()

    raw, messages = collect(content)
    assert requested == [URL], requested  # one download for the two datasets (reduce_dataset_list)
    stored = raw._mongo_database.documents
    fragments = [d.get("FragmentNumber") for d in stored]
    (reassembled,) = raw.fetch_raw_data(metadata.get_source_info("VDEM_RULELW"))
    raw_source = reassembled["Source"]

    # ----------------------------------------------------------------- score
    captured, outcomes = {}, {}
    original_score_indicator = utilities.score_indicator

    def capturing_score_indicator(documents, indicator_code, score_function, unit, *a, **k):
        captured.setdefault(indicator_code, score_function)
        outcomes[indicator_code] = original_score_indicator(documents, indicator_code, score_function, unit, *a, **k)
        return outcomes[indicator_code]

    for indicator, (code, column) in DATASETS.items():
        cleaned = clean(raw, code, EVALUATION_DATE)
        earlier = clean(raw, code, EARLIER_EVALUATION_DATE) if not args.real else None
        table = pd.read_csv(io.StringIO(reassembled["Raw"]), usecols=["country_text_id", "year", column])
        in_window = table[(table["year"] > 1990) & (table["year"] < EVALUATION_DATE.year)]
        write(
            out,
            f"vdem_{indicator.lower()}{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        "sspi_flask_app.api.core.dataset.collect_iterator (the collect route's iterator, both datasets; requests.get answering with the archive; sspi_raw_api_data = SSPIRawAPIData over an in-memory collection)",
                        f"{cleaner_modules[code].__name__}.clean_{code.lower()} (registered @dataset_cleaner, datetime.now() fixed, legacy insert validation applied)",
                    ],
                    fixture,
                ),
                "dataset_code": code,
                "source_column": column,
                "requested_urls": requested,
                "raw_source_info": raw_source,
                "raw_documents": len(stored),
                "raw_fragments": fragments,
                "raw_text_characters": len(reassembled["Raw"]),
                "collector_messages": messages,
                "evaluation_date": EVALUATION_DATE.isoformat(),
                "observations": observation_records(cleaned),
                "empty_source_values": int(in_window[column].isna().sum()),
                "legacy_document_keys": sorted({k for d in cleaned for k in d}),
                **(
                    {"earlier_evaluation": {"evaluation_date": EARLIER_EVALUATION_DATE.isoformat(), "observations": observation_records(earlier)}}
                    if earlier is not None
                    else {}
                ),
                "invalid_variants": {name: errors[code] for name, errors in variants.items()},
            },
        )
        print(f"{code}{suffix}: {len(cleaned)} observations ({min(d['Year'] for d in cleaned)}-{max(d['Year'] for d in cleaned)}), raw documents {len(stored)}, empty {int(in_window[column].isna().sum())}")

        module = importlib.import_module(f"sspi_flask_app.api.core.sspi.pg.rts.{indicator.lower()}")
        module.app, module.parse_json, module.sspi_metadata = logger, (lambda value: value), metadata
        module.score_indicator = capturing_score_indicator
        compute, impute = unwrap(getattr(module, f"compute_{indicator.lower()}")), unwrap(getattr(module, f"impute_{indicator.lower()}"))

        def fresh(clean_documents, module=module):
            module.sspi_clean_api_data = MongoStub("sspi_clean_api_data", clean_documents)
            module.sspi_indicator_data = validating("sspi_indicator_data", sspi_indicator_data)
            module.sspi_imputed_data = validating("sspi_imputed_data", sspi_imputed_data)

        def held(module=module):
            docs = module.sspi_indicator_data.documents
            counts = {}
            for d in docs:
                counts[(d["CountryCode"], d["Year"])] = counts.get((d["CountryCode"], d["Year"]), 0) + 1
            return {
                "sspi_indicator_data": len(docs),
                "sspi_indicator_data_imputed": sum(1 for d in docs if any(x.get("Imputed") for x in d["Datasets"])),
                "sspi_indicator_data_identities_held_twice": sum(1 for n in counts.values() if n > 1),
                "sspi_imputed_data": len(module.sspi_imputed_data.documents),
            }

        fresh(cleaned)
        observed = compute()
        _, incomplete = outcomes[indicator]
        imputed = impute()
        storage = {"compute_then_impute": held()}
        impute()
        storage["then_impute_again"] = held()
        compute()
        storage["then_compute_again"] = held()
        fresh(cleaned)
        impute()
        compute()
        storage["impute_then_compute"] = held()
        fresh([])
        empty = {"observed_scores": records(compute(), imputation=True), "imputed_scores": records(impute(), imputation=True)}
        conflicts_observed = {(d["CountryCode"], d["Year"]) for d in observed}
        counted = {}
        for d in imputed:
            counted[(d["CountryCode"], d["Year"])] = counted.get((d["CountryCode"], d["Year"]), 0) + 1
        front = frontmatter(f"methodology/pg/rts/{indicator.lower()}/methodology.md")
        lg, ug = front["LowerGoalpost"], front["UpperGoalpost"]
        write(
            out,
            f"{indicator.lower()}{suffix}_cases.json",
            {
                "generated_from": generated_from(
                    [
                        f"registered @dataset_cleaner function for {code} (as in vdem_{indicator.lower()}{suffix}_cases.json)",
                        f"{module.__name__}.compute_{indicator.lower()} (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                        f"{module.__name__}.impute_{indicator.lower()} (unwrapped view function, collection handles stubbed, legacy insert validation applied)",
                    ],
                    fixture,
                ),
                "indicator_code": indicator,
                "formula": f"goalpost({code}, {lg}, {ug})",
                "methodology_score_function": front["ScoreFunction"].strip(),
                "methodology_description": front["Description"].strip(),
                "goalposts": [lg, ug],
                "unit": next(iter({d["Unit"] for d in observed})),
                "imputed_unit": next(iter({d["Unit"] for d in imputed})) if imputed else None,
                "impute_route_exists": True,
                "impute_route_clears": "sspi_imputed_data",
                "impute_route_inserts_into": "sspi_indicator_data",
                "series_fill": {"order": ["forward"], "forward_to": 2023, "backward_to": None, "interpolation": None, "series_id": ["CountryCode", "DatasetCode"], "impute_only": True},
                "evaluation_date": EVALUATION_DATE.isoformat(),
                "observed_scores": records(observed, imputation=True),
                "incomplete_identities": identities(incomplete),
                "imputed_scores": records(imputed, imputation=True),
                "legacy_impute_error": None,
                "legacy_output_conflicts": {
                    "observed_and_imputed": [list(i) for i in sorted(conflicts_observed & set(counted))],
                    "duplicate_imputed": [list(i) for i in sorted(i for i, n in counted.items() if n > 1)],
                },
                "legacy_storage": storage,
                "empty_dataset": empty,
                "score_function_cases": [{"case": name, "input": value, "score": captured[indicator](value)} for name, value in SCORE_FUNCTION_CASES],
            },
        )
        print(f"{indicator}{suffix}: {len(observed)} observed, {len(imputed)} imputed; storage {storage}")


if __name__ == "__main__":
    main()
