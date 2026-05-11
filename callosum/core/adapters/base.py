"""Abstract base class for all LLM backend adapters."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from callosum.schemas.prompt import PromptBlock
from callosum.schemas.request import CompiledRequest
from callosum.schemas.cache import CacheUsage, CacheTrace


class BaseAdapter(ABC):
    """Abstract base for all LLM backend adapters.

    Each adapter MUST implement its own token counting and prefix
    hashing logic, bound to the exact tokenizer of its target backend.
    """

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the unique adapter identifier (e.g., 'anthropic', 'openai')."""
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens using the exact tokenizer of this adapter's backend.

        OpenAI-backed adapters MUST use tiktoken.
        Anthropic-backed adapters MUST use the Anthropic tokenizer.
        vLLM / SGLang adapters SHOULD use the backend's native tokenizer API.
        """
        pass

    @abstractmethod
    def get_prefix_hash(self, blocks: List[PromptBlock]) -> str:
        """Compute a prefix hash bound to this adapter and model.

        Format: {adapter_name}:{sha256(concatenated_static_blocks)}
        """
        pass

    @abstractmethod
    async def forward(
        self,
        compiled: CompiledRequest,
        trace_id: str,
        callosum_headers: Dict[str, str] | None = None,
    ) -> Tuple[Any, CacheTrace]:
        """Forward compiled request to backend and return response with cache trace."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if backend is healthy and reachable."""
        pass

    @abstractmethod
    def extract_cache_usage(self, response: Any) -> CacheUsage:
        """Extract actual cache usage from backend API response."""
        pass

    @abstractmethod
    def normalize_response(self, response: Any) -> Dict[str, Any]:
        """Convert backend-specific response to OpenAI Chat Completion format."""
        pass
