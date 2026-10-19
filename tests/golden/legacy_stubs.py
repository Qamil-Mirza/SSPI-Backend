"""Legacy-side helpers shared by the golden generators: an in-memory Mongo
collection that answers the query operators the legacy routes use, and the
World Bank cleaner's skip accounting.

Run inside the old repository's virtualenv, like the generators that import
it (``PYTHONPATH=<this directory>``).
"""

from __future__ import annotations

import json

_ABSENT = object()


def mongo_match(document, query):
    """MongoDB's answer for the operators the stubbed legacy routes use; a missing field matches nothing."""
    for key, wanted in query.items():
        value = document.get(key, _ABSENT)
        if isinstance(wanted, dict):
            for operator, operand in wanted.items():
                if operator == "$in":
                    if value is _ABSENT or value not in operand:
                        return False
                elif operator == "$gte":
                    if value is _ABSENT or not value >= operand:
                        return False
                else:
                    raise AssertionError(f"operator {operator} not used by the legacy routes stubbed here")
        elif value is _ABSENT or value != wanted:
            return False
    return True


class MongoStub:
    """An in-memory collection; logs every query with the number of documents it returned."""

    def __init__(self, name, documents=(), log=None):
        self.name, self.documents = name, [json.loads(json.dumps(d)) for d in documents]
        self.log = log if log is not None else []  # may be shared by several collections, for one chronological record

    def find(self, query):
        found = [json.loads(json.dumps(d)) for d in self.documents if mongo_match(d, query)]  # fresh copies, as Mongo would return
        self.log.append({"collection": self.name, "operation": "find", "query": query, "returned": len(found)})
        return found

    def delete_many(self, query):
        before = len(self.documents)
        self.documents = [d for d in self.documents if not mongo_match(d, query)]
        self.log.append({"collection": self.name, "operation": "delete_many", "query": query, "returned": before - len(self.documents)})
        return before - len(self.documents)

    def insert_many(self, documents):
        self.documents.extend(json.loads(json.dumps(documents)))
        self.log.append({"collection": self.name, "operation": "insert_many", "returned": len(documents)})
        return len(documents)


def legacy_skipped(rows):
    """What the legacy cleaner dropped before its value test: areas pycountry does not know (by the code it
    looked up: ``countryiso3code``, else ``country.id``), and how many rows had neither code."""
    from pycountry import countries

    skipped, without_code, missing = {}, 0, 0
    for row in rows:
        code = row["countryiso3code"] or row["country"]["id"]
        if not code:
            without_code += 1
        elif countries.get(alpha_3=code) is None:
            skipped[(code, row["country"]["value"])] = None
        elif not row["value"] or row["value"] == "NaN":
            missing += 1
    return [list(s) for s in sorted(skipped)], without_code, missing
