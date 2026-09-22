"""SSPI methodology metadata: indicators, datasets, and their dependencies.

Importing this package reads no files. Call ``MetadataCatalog.load()`` to
parse the bundled YAML once and query it in memory.
"""

from sspi.metadata.catalog import MetadataCatalog, bundled_data_root
from sspi.metadata.models import DatasetMetadata, IndicatorMetadata, SourceMetadata, UnresolvedDataset

__all__ = [
    "DatasetMetadata",
    "IndicatorMetadata",
    "MetadataCatalog",
    "SourceMetadata",
    "UnresolvedDataset",
    "bundled_data_root",
]
