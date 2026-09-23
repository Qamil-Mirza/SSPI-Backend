"""Country identity and SSPI country groups, from ``country_groups.yaml``.

The file is a verbatim copy of the legacy ``local/country-groups.json``:
groups in source order, members in source order, memberships unchanged.
Nothing here sorts, corrects or reinterprets them. As the legacy loader did,
the country universe is the union of all group members and country names
come from pycountry at load time; no other country attribute exists.

Layout::

    groups:
    - code: SSPI49
      members: [ARG, AUS, ...]
    - code: ...

Validation collects every problem and raises them together in one
``MetadataError``. Unlike the legacy loader, a member code pycountry does not
recognise is an error rather than a silently missing country.

Nothing runs at import time; ``CountryCatalog.load`` is the only entry point
that touches the filesystem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import pycountry

from sspi.errors import UnknownCodeError
from sspi.metadata.catalog import bundled_data_root
from sspi.metadata.loader import _check_keys, _Problems, read_yaml

COUNTRY_GROUPS_FILE = "country_groups.yaml"
TOP_LEVEL_KEYS = frozenset({"groups"})
GROUP_KEYS = frozenset({"code", "members"})
ALPHA3 = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class CountryGroup:
    """One named set of countries, members in legacy source order."""

    code: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Country:
    """ISO 3166-1 alpha-3 identity plus the groups it belongs to, in legacy group order."""

    code: str
    name: str
    groups: tuple[str, ...]


def _country_name(code: str) -> str | None:
    country = pycountry.countries.get(alpha_3=code)
    return None if country is None else country.name


def load_country_groups(path: Path) -> tuple[CountryGroup, ...]:
    """Read and validate one country-groups file, preserving its order."""
    path = Path(path)
    problems = _Problems(path.parent)
    if not path.is_file():
        problems.add(path, "file does not exist")
    problems.raise_if_any()

    data = read_yaml(path)
    if not isinstance(data, dict):
        problems.add(path, f"top level must be a mapping, got {type(data).__name__}")
        problems.raise_if_any()
    _check_keys(data, TOP_LEVEL_KEYS, path, problems)
    if "groups" not in data:
        problems.add(path, "missing required field 'groups'")
        problems.raise_if_any()
    entries = data["groups"]
    if not isinstance(entries, list) or not entries:
        problems.add(path, f"field 'groups' must be a non-empty list, got {entries!r}")
        problems.raise_if_any()

    groups: dict[str, CountryGroup] = {}
    for index, entry in enumerate(entries):
        context = f"groups[{index}]."
        if not isinstance(entry, dict):
            problems.add(path, f"{context[:-1]} must be a mapping, got {entry!r}")
            continue
        _check_keys(entry, GROUP_KEYS, path, problems, context)
        code = entry.get("code")
        if not isinstance(code, str) or not code:
            problems.add(path, f"field {context}'code' must be a non-empty string, got {code!r}")
            code = None
        members = entry.get("members")
        if not isinstance(members, list) or not members:
            problems.add(path, f"field {context}'members' must be a non-empty list, got {members!r}")
            continue
        label = code or f"groups[{index}]"
        seen: set[str] = set()
        for member in members:
            if not isinstance(member, str) or not ALPHA3.match(member) or _country_name(member) is None:
                problems.add(path, f"member {member!r} in group {label} is not a current ISO 3166-1 alpha-3 code")
            elif member in seen:
                problems.add(path, f"duplicate member {member!r} in group {label}")
            seen.add(member if isinstance(member, str) else repr(member))
        if code is None:
            continue
        if code in groups:
            problems.add(path, f"duplicate group code {code}")
            continue
        groups[code] = CountryGroup(code=code, members=tuple(members))

    problems.raise_if_any()
    return tuple(groups.values())


@dataclass(frozen=True)
class CountryCatalog:
    """Which countries exist, and which SSPI groups is each one in?

    Construct with :meth:`load`. Instances are immutable and cheap to query.
    Orderings are the legacy source orderings: ``groups()`` and each
    ``Country.groups`` follow file order, ``members`` follow list order, and
    ``countries()`` are sorted by code as the legacy country details were.
    """

    _groups: Mapping[str, CountryGroup]
    _countries: Mapping[str, Country] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str | None = None) -> CountryCatalog:
        """Read and validate the country-groups file.

        Defaults to the file bundled with the package. Raises ``MetadataError``
        listing every problem if the file is invalid.
        """
        groups = load_country_groups(bundled_data_root() / COUNTRY_GROUPS_FILE if path is None else Path(path))
        memberships: dict[str, list[str]] = {}
        for group in groups:
            for member in group.members:
                memberships.setdefault(member, []).append(group.code)
        countries = {
            code: Country(code=code, name=_country_name(code) or code, groups=tuple(memberships[code]))
            for code in sorted(memberships)
        }
        return cls(
            _groups=MappingProxyType({g.code: g for g in groups}),
            _countries=MappingProxyType(countries),
        )

    def group(self, code: str) -> CountryGroup:
        try:
            return self._groups[code]
        except KeyError:
            raise UnknownCodeError(f"unknown country group {code!r}") from None

    def groups(self) -> tuple[CountryGroup, ...]:
        return tuple(self._groups.values())

    def country(self, code: str) -> Country:
        try:
            return self._countries[code]
        except KeyError:
            raise UnknownCodeError(f"unknown country code {code!r} (not a member of any group)") from None

    def countries(self) -> tuple[Country, ...]:
        return tuple(self._countries.values())

    def groups_for(self, country_code: str) -> tuple[str, ...]:
        return self.country(country_code).groups
