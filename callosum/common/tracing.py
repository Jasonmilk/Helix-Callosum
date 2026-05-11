"""Distributed trace context propagation."""

from contextvars import ContextVar
import structlog

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def extract_trace_id(headers: dict) -> str:
    """Extract trace_id from traceparent or X-Trace-Id header.

    Args:
        headers: Request headers dictionary.

    Returns:
        Extracted trace ID string.
    """
    traceparent = headers.get("traceparent", "")
    if traceparent and len(traceparent) >= 36:
        return traceparent[3:35]
    return headers.get("x-trace-id", "")


def set_trace_context(trace_id: str) -> None:
    """Set trace context for the current execution context.

    Args:
        trace_id: Trace ID to bind to logging context.
    """
    _trace_id_var.set(trace_id)
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
