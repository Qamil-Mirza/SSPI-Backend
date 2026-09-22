"""In-memory catalog of SSPI methodology metadata.

Loaded once from the canonical YAML files; every query afterwards is a
dictionary lookup. No database, environment, or network involvement.
"""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from sspi.errors import UnknownCodeError
from sspi.metadata.loader import load_catalog_data
from sspi.metadata.models import DatasetMetadata, IndicatorMetadata, UnresolvedDataset


def bundled_data_root() -> Path:
    """Directory holding the metadata shipped inside the ``sspi`` package."""
    return Path(str(importlib.resources.files("sspi.metadata"))) / "data"


@dataclass(frozen=True, slots=True)
class MetadataCatalog:
    """What is indicator X, and which datasets does it depend on?

    Construct with :meth:`load`. Instances are immutable and cheap to query.
    """

    _indicators: Mapping[str, IndicatorMetadata]
    _datasets: Mapping[str, DatasetMetadata | UnresolvedDataset]
    _users: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str | None = None) -> MetadataCatalog:
        """Read and validate the metadata tree under ``root``.

        Defaults to the metadata bundled with the package. Raises
        ``MetadataError`` listing every problem if the tree is invalid.
        """
        data = load_catalog_data(bundled_data_root() if root is None else Path(root))
        users: dict[str, list[str]] = {code: [] for code in data.datasets}
        for indicator in sorted(data.indicators.values(), key=lambda i: i.code):
            for dataset_code in indicator.dataset_codes:
                users[dataset_code].append(indicator.code)
        return cls(
            _indicators=MappingProxyType(dict(sorted(data.indicators.items()))),
            _datasets=MappingProxyType(dict(sorted(data.datasets.items()))),
            _users=MappingProxyType({code: tuple(codes) for code, codes in users.items()}),
        )

    # --- single lookups ---------------------------------------------------

    def indicator(self, code: str) -> IndicatorMetadata:
        try:
            return self._indicators[code]
        except KeyError:
            raise UnknownCodeError(f"unknown indicator code {code!r}") from None

    def dataset(self, code: str) -> DatasetMetadata | UnresolvedDataset:
        try:
            return self._datasets[code]
        except KeyError:
            raise UnknownCodeError(f"unknown dataset code {code!r}") from None

    # --- listings -----------------------------------------------------------

    def indicators(self) -> tuple[IndicatorMetadata, ...]:
        return tuple(self._indicators.values())

    def datasets(self) -> tuple[DatasetMetadata, ...]:
        """Datasets with a complete definition, sorted by code."""
        return tuple(d for d in self._datasets.values() if isinstance(d, DatasetMetadata))

    def unresolved_datasets(self) -> tuple[UnresolvedDataset, ...]:
        return tuple(d for d in self._datasets.values() if isinstance(d, UnresolvedDataset))

    # --- relationships --------------------------------------------------------

    def dataset_dependencies(self, indicator_code: str) -> tuple[DatasetMetadata | UnresolvedDataset, ...]:
        """The datasets an indicator is computed from, in declared order."""
        return tuple(self._datasets[code] for code in self.indicator(indicator_code).dataset_codes)

    def indicators_using(self, dataset_code: str) -> tuple[IndicatorMetadata, ...]:
        """Indicators that list ``dataset_code`` among their dependencies, sorted by code."""
        self.dataset(dataset_code)  # raises UnknownCodeError for unknown codes
        return tuple(self._indicators[code] for code in self._users.get(dataset_code, ()))
