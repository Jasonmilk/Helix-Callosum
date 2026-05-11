"""Cache trace and usage DTOs."""

from pydantic import BaseModel, Field
from typing import Optional


class CacheUsage(BaseModel):
    """Cache usage extracted from backend API response."""
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class CacheTrace(BaseModel):
    """Audit record for a single cache interaction."""
    hit_predicted: bool
    hit_verified: Optional[bool] = None
    prefix_hash: str
    saved_tokens_estimated: int
    saved_tokens_verified: Optional[int] = None
    saved_cost_usd: float = 0.0
