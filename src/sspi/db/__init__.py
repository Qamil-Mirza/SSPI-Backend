"""PostgreSQL persistence for dynamic SSPI data (observations and scores).

Importing this package builds no engine and opens no connection. Construct a
``Database`` explicitly, then use ``Repository`` inside ``Database.transaction()``.
"""

from sspi.db.engine import Database
from sspi.db.repository import Repository

__all__ = ["Database", "Repository"]
