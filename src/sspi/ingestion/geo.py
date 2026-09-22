"""Geography helpers for source ingestion.

The UN SDG API identifies areas by UN M49 numeric codes. For countries these
coincide with ISO 3166-1 numeric codes, so pycountry resolves them to ISO3.
Regional aggregates (World, Europe, LDCs, ...) and areas without an ISO entry
resolve to ``None``; callers decide what to do with those.
"""

from __future__ import annotations

import pycountry


def m49_to_iso3(code: str | int) -> str | None:
    """ISO 3166-1 alpha-3 for an M49 numeric code, or ``None`` if not a country."""
    try:
        numeric = f"{int(code):03d}"
    except (TypeError, ValueError):
        return None
    country = pycountry.countries.get(numeric=numeric)
    return country.alpha_3 if country is not None else None
