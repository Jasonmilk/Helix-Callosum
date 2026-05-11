"""Pydantic DTO contracts for cross-module communication."""

from .exceptions import (
    CallosumBaseError,
    CompilationError,
    VFDResolutionError,
    BackendUnavailableError,
    CacheVerificationMismatch,
)
from .prompt import VolatilityLevel, PromptBlock
from .request import CallosumRequest, CompiledRequest
from .cache import CacheUsage, CacheTrace

__all__ = [
    # Exceptions
    "CallosumBaseError",
    "CompilationError",
    "VFDResolutionError",
    "BackendUnavailableError",
    "CacheVerificationMismatch",
    # Prompt
    "VolatilityLevel",
    "PromptBlock",
    # Request
    "CallosumRequest",
    "CompiledRequest",
    # Cache
    "CacheUsage",
    "CacheTrace",
]
