"""Source ingestion: fetch external data and normalize it into Observations.

Importing this package performs no network or database activity. Persistence
is never done here; callers pass normalized observations to
``sspi.db.Repository`` explicitly.
"""

from sspi.ingestion.unsdg import NormalizationResult, UNSDGClient, normalize_unsdg_dataset

__all__ = ["NormalizationResult", "UNSDGClient", "normalize_unsdg_dataset"]
