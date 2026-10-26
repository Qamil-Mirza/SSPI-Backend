"""Local source files: sources the legacy SSPI read from a file kept beside
the code, not from an API or a download.

The legacy ITU collector and cleaner (``api/datasource/itu.py``) read the
SSPI's own hand transcription of the ITU Global Cybersecurity Index scores,
``local/gci-local-indicator-summary.csv``, from the working directory of the
legacy application. There is no ITU address to request: the file is the
source.

A local file is named by a key, the dataset's canonical ``query_code``.
:data:`LOCAL_FILES` maps each key to the edition it is, its path below the
local source directory, the SHA-256 of its bytes and where the file comes
from. The directory defaults to :data:`DEFAULT_ROOT`, the repository's
``local-data/`` (git-ignored); pass ``root`` to read from elsewhere. The
client refuses a missing file and a file whose bytes differ from the pin:
no other file, and no other version of the same file, is ever substituted.
A caller may pass its own ``files`` table to read another file explicitly.

Nothing here parses a file; the organization's normalizer does
(:mod:`sspi.ingestion.itu`). Nothing here touches a database.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sspi.config import PROJECT_ROOT
from sspi.errors import SourceRequestError, SourceResponseError

DEFAULT_ROOT = PROJECT_ROOT / "local-data"


@dataclass(frozen=True, slots=True)
class LocalSourceFile:
    """One version of one local source file."""

    edition: str
    path: str  # relative to the client's root
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned file)
    origin: str  # where the pinned bytes come from


@dataclass(frozen=True, slots=True)
class LocalFile:
    """A read file: its canonical key, the version it was configured as, where it was read, its checksum and bytes."""

    key: str
    source: LocalSourceFile
    location: str
    sha256: str
    content: bytes


# Local file (canonical query_code) -> what and where it is.
LOCAL_FILES: dict[str, LocalSourceFile] = {
    # The SSPI's hand transcription of the ITU Global Cybersecurity Index (editions 2014, 2017, 2018, 2020 and
    # 2024), committed to the legacy repository as local/gci-local-indicator-summary.csv and moved, unchanged, to
    # local/CYBSEC/ on 2025-03-27 (170274b32); the pinned collector and cleaner still read the old path. 11,308
    # bytes, 196 countries. Licence terms open: docs/data-governance-review.md, GOV-4.
    "gci-local-indicator-summary": LocalSourceFile(
        edition="SSPI transcription of ITU Global Cybersecurity Index scores, editions 2014, 2017, 2018, 2020 and 2024",
        path="itu/gci-local-indicator-summary.csv",
        sha256="f438b04d231799d6957ac81d02ad9db65dcc75a34b77bfc15654f52e5ae739b9",
        origin="sspi-data-webapp@76f842b08e551dfa8fb9563e4c812be086654ba6:local/CYBSEC/gci-local-indicator-summary.csv",
    ),
}


class LocalFileClient:
    """Reads configured local source files.

    ``files`` maps keys to :class:`LocalSourceFile` and defaults to
    :data:`LOCAL_FILES`; ``root`` is the directory their paths are relative
    to and defaults to :data:`DEFAULT_ROOT`.
    """

    def __init__(self, *, root: str | Path | None = None, files: Mapping[str, LocalSourceFile] | None = None) -> None:
        self.root = Path(DEFAULT_ROOT if root is None else root)
        self.files = dict(LOCAL_FILES if files is None else files)

    def fetch_file(self, key: str) -> LocalFile:
        """Read one configured file and check its bytes against the configured checksum."""
        try:
            source = self.files[key]
        except KeyError:
            raise SourceRequestError(f"no local source file is configured for {key!r}; known: {sorted(self.files)}") from None
        path = self.root / source.path
        if not path.is_file():
            raise SourceRequestError(f"local source file {key!r} is not at {path}; it is {source.edition!r}, from {source.origin}")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"local source file {key!r} ({path}) has SHA-256 {digest}, not the configured {source.sha256} of {source.edition!r} "
                f"({source.origin}): the file changed; no other version is substituted"
            )
        return LocalFile(key, source, str(path), digest, content)

    def close(self) -> None:
        pass

    def __enter__(self) -> LocalFileClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
