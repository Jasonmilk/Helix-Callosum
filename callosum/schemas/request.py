"""Request and compilation result DTOs."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from .prompt import PromptBlock


class CallosumRequest(BaseModel):
    """Unified request from calling Agent.

    All parameters are atomic and generic — no cognitive mode is predefined.
    The calling Agent combines them to express its strategy.
    """
    blocks: List[PromptBlock]
    cache_strategy: Literal["aggressive", "balanced", "isolated"] = "aggressive"
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    attention_boost: bool = False
    thinking_transient: bool = False
    sandbox_namespace: str = ""
    footer_slot_enabled: bool = False
    trace_id: str


class CompiledRequest(BaseModel):
    """Output of Iceberg Compiler: cache-optimized blocks."""
    blocks: List[PromptBlock]
    cache_breakpoints: List[int] = Field(default_factory=list)
    prefix_hash: str
    total_tokens: int
    estimated_savings: int
