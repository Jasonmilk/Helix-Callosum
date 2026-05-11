"""OpenAI backend adapter."""

import httpx
from typing import Any, Dict, List, Tuple
from callosum.schemas.request import CompiledRequest
from callosum.schemas.cache import CacheUsage, CacheTrace
from callosum.common.config import Settings
from callosum.common.utils import generate_span_id, compute_sha256
from .base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI API backend."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://api.openai.com/v1"

    def get_adapter_name(self) -> str:
        return "openai"

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken for OpenAI."""
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    def get_prefix_hash(self, blocks: List) -> str:
        """Compute adapter-specific prefix hash."""
        static_blocks = [b for b in blocks if b.volatility and b.volatility.score <= 1]
        static_text = "".join(b.content for b in static_blocks)
        content_hash = compute_sha256(static_text)
        return f"openai:{content_hash}"

    async def forward(
        self,
        compiled: CompiledRequest,
        trace_id: str,
        callosum_headers: Dict[str, str] | None = None,
    ) -> Tuple[Any, CacheTrace]:
        """Forward compiled request to OpenAI API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.openai_api_key or ''}",
            "traceparent": f"00-{trace_id}-{generate_span_id()}-01",
        }
        if callosum_headers:
            headers.update(callosum_headers)

        messages = [{"role": b.role, "content": b.content} for b in compiled.blocks]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.openai_model,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        cache_usage = self.extract_cache_usage(data)
        cache_trace = CacheTrace(
            hit_predicted=False,
            hit_verified=cache_usage.cache_read_input_tokens > 0,
            prefix_hash=compiled.prefix_hash,
            saved_tokens_estimated=compiled.estimated_savings,
            saved_tokens_verified=cache_usage.cache_read_input_tokens,
        )
        return data, cache_trace

    async def health_check(self) -> bool:
        """Check if OpenAI API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def extract_cache_usage(self, response: Any) -> CacheUsage:
        """Extract cache usage from OpenAI response."""
        usage = response.get("usage", {})
        details = usage.get("prompt_tokens_details", {})
        return CacheUsage(
            cache_creation_input_tokens=0,
            cache_read_input_tokens=details.get("cached_tokens", 0),
        )

    def normalize_response(self, response: Any) -> Dict[str, Any]:
        """OpenAI response is already in the standard format."""
        return response