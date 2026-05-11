"""Structured logging configuration."""

import structlog


def configure_logging() -> None:
    """Configure structlog for structured JSON logging with context."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


logger = structlog.get_logger()
