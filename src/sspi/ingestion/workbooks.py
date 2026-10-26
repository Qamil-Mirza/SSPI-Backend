"""Pinned source workbooks: one edition of one published file, identified by
its original file name, edition, revision date, official URL and the SHA-256
of its bytes.

:class:`PinnedWorkbookClient` obtains a configured workbook either by
downloading it from its official URL or, when the caller passes
``local_directory``, from an explicitly configured local copy of the same
file (``<local_directory>/<file name>``), for offline reproduction. Either
way the bytes must match the pinned checksum exactly: a changed workbook, at
the same address or under the same name, is refused, and no other edition
is substituted. Nothing here has a default local path; a local copy is read
only when the caller names its directory.

Source adapters own their table of :class:`PinnedWorkbook` and the parsing
of the workbook; this module only acquires and verifies bytes. Nothing here
touches a database.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

from sspi.errors import SourceRequestError, SourceResponseError


@dataclass(frozen=True, slots=True)
class PinnedWorkbook:
    """One edition of one published workbook."""

    filename: str  # the file name as published
    edition: str  # the publisher's edition, in words
    revised: str  # the revision date the publisher states (ISO date)
    url: str  # the official download address
    landing_page: str  # the official page that links and describes the file
    sha256: str  # SHA-256 of the exact bytes
    retrieved: str  # date the pinned bytes were verified at the URL


@dataclass(frozen=True, slots=True)
class WorkbookFile:
    """An obtained workbook: its key, the pinned edition, where the bytes came from, and the bytes."""

    key: str
    source: PinnedWorkbook
    origin: str  # the URL downloaded, or "local copy: <path>"
    content: bytes


class PinnedWorkbookClient:
    """Obtains pinned workbooks by download or from an explicitly configured local copy.

    ``workbooks`` maps keys (a dataset's canonical ``query_code``) to
    :class:`PinnedWorkbook`. ``local_directory``, when given, is read instead
    of the network. ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created on first download and owned
    by this object.
    """

    def __init__(
        self,
        workbooks: Mapping[str, PinnedWorkbook],
        *,
        local_directory: str | Path | None = None,
        http: httpx.Client | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.workbooks = dict(workbooks)
        self.local_directory = None if local_directory is None else Path(local_directory)
        self._http = http
        self._owns_http = http is None
        self._timeout = timeout

    def fetch_workbook(self, key: str) -> WorkbookFile:
        """The pinned workbook's bytes, verified against its checksum."""
        try:
            source = self.workbooks[key]
        except KeyError:
            raise SourceRequestError(f"no pinned workbook is configured for {key!r}; known: {sorted(self.workbooks)}") from None
        if self.local_directory is not None:
            path = self.local_directory / source.filename
            if not path.is_file():
                raise SourceRequestError(f"the configured local copy of workbook {key!r} is not at {path}; it is {source.filename}, {source.edition}, from {source.url}")
            content, origin = path.read_bytes(), f"local copy: {path}"
        else:
            if self._http is None:
                self._http = httpx.Client(timeout=self._timeout, follow_redirects=True)
            try:
                response = self._http.get(source.url)
            except httpx.HTTPError as exc:
                raise SourceRequestError(f"workbook request for {key!r} failed: {exc}") from exc
            if response.status_code != 200:
                raise SourceRequestError(f"workbook request for {key!r} returned HTTP {response.status_code} ({source.url})")
            content, origin = response.content, source.url
        digest = hashlib.sha256(content).hexdigest()
        if digest != source.sha256:
            raise SourceResponseError(
                f"workbook {key!r} ({origin}) has SHA-256 {digest}, not the pinned {source.sha256} of {source.filename} "
                f"({source.edition}, revised {source.revised}): the file changed; no other edition is substituted"
            )
        return WorkbookFile(key, source, origin, content)

    def close(self) -> None:
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None

    def __enter__(self) -> PinnedWorkbookClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
