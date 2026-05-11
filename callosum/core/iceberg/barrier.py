"""Cache barrier detection utilities."""

BARRIER_MARKER = "<callosum-barrier>"


def detect_barrier(block_content: str) -> bool:
    """Return True if the block contains the cache barrier marker."""
    return BARRIER_MARKER in block_content


def strip_barrier(content: str) -> str:
    """Remove barrier marker from content for actual prompt construction."""
    return content.replace(BARRIER_MARKER, "")
