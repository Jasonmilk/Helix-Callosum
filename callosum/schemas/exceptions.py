"""Exception hierarchy for Helix-Callosum."""


class CallosumBaseError(Exception):
    """Base class for all Helix-Callosum exceptions."""
    pass


class CompilationError(CallosumBaseError):
    """Iceberg compiler failed to process prompt."""
    pass


class VFDResolutionError(CallosumBaseError):
    """vFD handle could not be resolved to actual content."""
    pass


class BackendUnavailableError(CallosumBaseError):
    """LLM backend is unhealthy or unreachable."""
    pass


class CacheVerificationMismatch(CallosumBaseError):
    """Shadow tree prediction did not match API reported cache hit."""
    pass
