"""SSPI backend and research data platform.

Importing this package connects to nothing, reads no configuration and no
metadata file. The researcher-facing entry point is ``from sspi import SSPI``;
it is loaded on first access so that the pure modules (scoring, imputation,
metadata) can be imported without pandas.
"""

from __future__ import annotations

__all__ = ["SSPI"]


def __getattr__(name: str):
    if name == "SSPI":
        from sspi.facade import SSPI

        return SSPI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
