"""Iceberg Compiler module for cache-optimal prompt reordering."""

from .compiler import IcebergCompiler
from .barrier import detect_barrier, strip_barrier

__all__ = ["IcebergCompiler", "detect_barrier", "strip_barrier"]
