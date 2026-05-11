"""Shared utility functions."""

import hashlib
import tiktoken
from typing import Optional

# Default tokenizer for rough token estimation (cl100k base used by GPT-4, Claude)
_default_encoding = tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    """Rough token count estimation using cl100k base encoding.

    This is used for general estimation. Adapters should use their backend-specific
    tokenizer for precise counting.

    Args:
        text: Input text to count tokens for.

    Returns:
        Estimated number of tokens.
    """
    return len(_default_encoding.encode(text))


def compute_sha256(text: str) -> str:
    """Compute SHA256 hash of input text.

    Args:
        text: Input text to hash.

    Returns:
        Hex-encoded SHA256 hash string.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_span_id() -> str:
    """Generate a random 8-byte span ID for W3C tracing.

    Returns:
        Hex-encoded span ID string.
    """
    import os
    return os.urandom(8).hex()