"""Executable indicators: the registry that binds an indicator code to its
Python implementation, and the runner that executes one against PostgreSQL.

Importing this package builds no engine, opens no connection and reads no
metadata file. ``sspi.indicators.registry`` alone imports no persistence code.
"""

from sspi.indicators import registry
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.runner import IndicatorRun, compute_indicator, run_indicator

__all__ = ["IndicatorDefinition", "IndicatorRun", "compute_indicator", "registry", "run_indicator"]
