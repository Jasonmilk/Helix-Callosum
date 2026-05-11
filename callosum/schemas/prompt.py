"""Prompt block and volatility classification DTOs."""

from pydantic import BaseModel, Field
from typing import Literal, Optional


class VolatilityLevel(BaseModel):
    """Volatility classification for a prompt block."""
    score: int = Field(..., ge=0, le=10, description="Volatility score (0 = static, 10 = highly dynamic)")
    reason: str = Field(..., description="e.g., 'system_prompt', 'tool_definition', 'user_code', 'dynamic_query'")


class PromptBlock(BaseModel):
    """Atomic unit of a prompt, classified by volatility and role."""
    content: str
    volatility: Optional[VolatilityLevel] = Field(None, description="Volatility classification; assigned by compiler if None")
    role: Literal["system", "tool", "vfd", "user", "dynamic"] = Field(..., description="Semantic role of this block")
    source: Optional[str] = Field(None, description="vFD handle or raw text origin")
    contains_barrier: bool = Field(False, description="True if <callosum-barrier> is present in this block")