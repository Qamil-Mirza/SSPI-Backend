"""Geography helpers for source ingestion.

The UN SDG API identifies areas by UN M49 numeric codes. For countries these
coincide with ISO 3166-1 numeric codes, so pycountry resolves them to ISO3.
Regional aggregates (World, Europe, LDCs, ...) and areas without an ISO entry
resolve to ``None``; callers decide what to do with those.

Sources that name countries in words (the ITU Global Cybersecurity Index
transcription) go through :func:`legacy_country_code`, the legacy name
matcher reproduced exactly.
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


def legacy_country_code(country_name: str) -> str:
    """The legacy name matcher (``get_country_code`` in
    ``api/resources/utilities.py`` at the pinned commit), reproduced rule for
    rule and in its order: a few substring rules, then ``pycountry``'s exact
    lookup by code or name (case-insensitive, accents significant). A name
    nothing matches comes back unchanged, as it did in legacy; callers decide
    what to do with a result that is not an ISO3 code.

    The substring rules are the legacy ones, quirks included: any name
    containing ``"korea"`` without ``"democratic"`` is KOR, ``"niger"``
    without ``"nigeria"`` is NER, and ``"dr"`` together with ``"congo"`` is COD.
    """
    name = str.lower(country_name)
    if "kosovo" in name:
        return "XKX"
    if "korea" in name and ("democratic" not in name or "south" in name):
        return "KOR"
    if "korea" in name and ("democratic" in name or "north" in name):
        return "PRK"
    if "niger" in name and "nigeria" not in name:
        return "NER"
    if "democratic republic" in name or "dr" in name and "congo" in name:
        return "COD"
    if "congo republic" in name:
        return "COG"
    if "guinea bissau" in name:
        return "GNB"
    if "laos" in name:
        return "LAO"
    if "kiye" in name:
        return "TUR"
    if "turkiye" in name or "turkey" in name:
        return "TUR"
    if "cape verde" in name:
        return "CPV"
    if "swaziland" in name:
        return "SWZ"
    if "israel and west bank" in name:
        return "ISR"
    if "gambia the" in name:
        return "GMB"
    if "timor leste" in name:
        return "TLS"
    if "russia" == name or "russian federation" in name:
        return "RUS"
    try:
        return pycountry.countries.lookup(country_name).alpha_3
    except LookupError:
        return country_name
