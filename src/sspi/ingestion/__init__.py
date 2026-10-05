"""Source ingestion: fetch external data and normalize it into Observations.

Importing this package performs no network or database activity. The
source clients and normalizers never persist anything; ``sspi.ingestion.runner``
orchestrates fetch, normalize and one ``Repository.replace_dataset`` per
requested dataset inside a single transaction.

Sources with an ingestion path: UN SDG Global Database (``unsdg``), FAOSTAT
bulk downloads (``fao``), Yale EPI edition archives (``epi``).
"""

from sspi.ingestion.epi import EPIClient, normalize_epi_dataset
from sspi.ingestion.fao import FAOBulkClient, normalize_fao_dataset
from sspi.ingestion.results import NormalizationResult
from sspi.ingestion.runner import SOURCES, SUPPORTED_DATASETS, DatasetIngestion, IngestionRun, ingest_datasets
from sspi.ingestion.unsdg import UNSDGClient, normalize_unsdg_dataset

__all__ = [
    "SOURCES",
    "SUPPORTED_DATASETS",
    "DatasetIngestion",
    "EPIClient",
    "FAOBulkClient",
    "IngestionRun",
    "NormalizationResult",
    "UNSDGClient",
    "ingest_datasets",
    "normalize_epi_dataset",
    "normalize_fao_dataset",
    "normalize_unsdg_dataset",
]
