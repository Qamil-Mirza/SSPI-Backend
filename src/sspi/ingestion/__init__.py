"""Source ingestion: fetch external data and normalize it into Observations.

Importing this package performs no network or database activity. The
source clients and normalizers never persist anything; ``sspi.ingestion.runner``
orchestrates fetch, normalize and one ``Repository.replace_dataset`` per
requested dataset inside a single transaction.

Sources with an ingestion path: UN SDG Global Database (``unsdg``), FAOSTAT
bulk downloads (``fao``), Yale EPI edition archives (``epi``), the World
Inequality Database bulk archive (``wid``), the World Bank Indicators API
(``worldbank``).
"""

from sspi.ingestion.epi import EPIClient, normalize_epi_dataset
from sspi.ingestion.fao import FAOBulkClient, normalize_fao_dataset
from sspi.ingestion.results import NormalizationResult
from sspi.ingestion.runner import SOURCES, SUPPORTED_DATASETS, DatasetIngestion, IngestionRun, ingest_datasets
from sspi.ingestion.unsdg import UNSDGClient, normalize_unsdg_dataset
from sspi.ingestion.wid import WIDClient, normalize_wid_dataset
from sspi.ingestion.worldbank import WorldBankClient, normalize_worldbank_dataset

__all__ = [
    "SOURCES",
    "SUPPORTED_DATASETS",
    "DatasetIngestion",
    "EPIClient",
    "FAOBulkClient",
    "IngestionRun",
    "NormalizationResult",
    "UNSDGClient",
    "WIDClient",
    "WorldBankClient",
    "ingest_datasets",
    "normalize_epi_dataset",
    "normalize_fao_dataset",
    "normalize_unsdg_dataset",
    "normalize_wid_dataset",
    "normalize_worldbank_dataset",
]
