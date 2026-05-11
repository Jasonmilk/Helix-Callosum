"""Tracing middleware for FastAPI."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from callosum.common.tracing import extract_trace_id, set_trace_context
from callosum.common.logging import logger


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and propagate trace context."""

    async def dispatch(self, request: Request, call_next):
        # Extract trace ID from request headers
        trace_id = extract_trace_id(dict(request.headers))
        set_trace_context(trace_id)
        
        # Process the request
        response: Response = await call_next(request)
        
        # Inject trace ID into response headers
        response.headers["X-Trace-Id"] = trace_id
        
        return response
