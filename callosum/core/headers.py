"""Callosum parameter header builder.

Converts request parameters into HTTP headers for backend propagation.
"""

from typing import Dict
from callosum.schemas.request import CallosumRequest, CompiledRequest


def build_callosum_headers(
    request: CallosumRequest,
    compiled: CompiledRequest,
) -> Dict[str, str]:
    """Build Callosum-specific HTTP headers for the backend request.

    Args:
        request: Original Callosum request.
        compiled: Compiled request.

    Returns:
        Dictionary of HTTP headers matching the specification.
    """
    headers = {}

    # Cache strategy
    if request.cache_strategy:
        headers["X-Callosum-Cache-Strategy"] = request.cache_strategy

    # Temperature
    headers["X-Callosum-Temperature"] = str(request.temperature)

    # Attention boost
    headers["X-Callosum-Attention-Boost"] = str(request.attention_boost).lower()

    # Thinking transient
    headers["X-Callosum-Thinking-Transient"] = str(request.thinking_transient).lower()

    # Sandbox namespace
    if request.sandbox_namespace:
        headers["X-Callosum-Sandbox-Namespace"] = request.sandbox_namespace

    # Footer slot
    headers["X-Callosum-Footer-Slot"] = str(request.footer_slot_enabled).lower()

    return headers