"""SSPI methodology metadata: indicators, datasets, their dependencies, and
country groups.

Importing this package reads no files. Call ``MetadataCatalog.load()`` or
``CountryCatalog.load()`` to parse the bundled YAML once and query it in memory.
"""

from sspi.metadata.catalog import MetadataCatalog, bundled_data_root
from sspi.metadata.countries import Country, CountryCatalog, CountryGroup
from sspi.metadata.models import DatasetMetadata, IndicatorMetadata, SourceMetadata, UnresolvedDataset

__all__ = [
    "Country",
    "CountryCatalog",
    "CountryGroup",
    "DatasetMetadata",
    "IndicatorMetadata",
    "MetadataCatalog",
    "SourceMetadata",
    "UnresolvedDataset",
    "bundled_data_root",
]
