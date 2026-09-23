"""Source ingestion: fetch external data and normalize it into Observations.

Importing this package performs no network or database activity. The
source client and normalizer never persist anything; ``sspi.ingestion.runner``
orchestrates fetch, normalize and one ``Repository.replace_dataset`` per
requested dataset inside a single transaction.
"""

from sspi.ingestion.runner import SUPPORTED_DATASETS, DatasetIngestion, IngestionRun, ingest_datasets
from sspi.ingestion.unsdg import NormalizationResult, UNSDGClient, normalize_unsdg_dataset

__all__ = ["SUPPORTED_DATASETS", "DatasetIngestion", "IngestionRun", "NormalizationResult", "UNSDGClient", "ingest_datasets", "normalize_unsdg_dataset"]
