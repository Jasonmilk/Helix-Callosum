"""Anthropic backend adapter."""

import httpx
from typing import Any, Dict, List, Tuple
from callosum.schemas.request import CompiledRequest
from callosum.schemas.cache import CacheUsage, CacheTrace
from callosum.common.config import Settings
from callosum.common.utils import generate_span_id, compute_sha256
from .base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Adapter for Anthropic API backend."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://api.anthropic.com/v1"

    def get_adapter_name(self) -> str:
        return "anthropic"

    async def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer."""
        import anthropic
        client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key or "")
        return await client.count_tokens(text)

    def get_prefix_hash(self, blocks: List) -> str:
        """Compute adapter-specific prefix hash."""
        static_blocks = [b for b in blocks if b.volatility and b.volatility.score <= 1]
        static_text = "".join(b.content for b in static_blocks)
        content_hash = compute_sha256(static_text)
        return f"anthropic:{content_hash}"

    async def forward(
        self,
        compiled: CompiledRequest,
        trace_id: str,
        callosum_headers: Dict[str, str] | None = None,
    ) -> Tuple[Any, CacheTrace]:
        """Forward compiled request to Anthropic API."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.settings.anthropic_api_key or "",
            "anthropic-version": "2023-06-01",
            "traceparent": f"00-{trace_id}-{generate_span_id()}-01",
        }
        if callosum_headers:
            headers.update(callosum_headers)

        # Convert compiled blocks to Anthropic message format
        messages = []
        for b in compiled.blocks:
            # Map roles that Anthropic understands
            role = b.role if b.role in ("user", "assistant") else "user"
            messages.append({"role": role, "content": b.content})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json={
                    "model": self.settings.anthropic_model,
                    "messages": messages,
                    "max_tokens": 4096,
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
        """Check if Anthropic API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def extract_cache_usage(self, response: Any) -> CacheUsage:
        """Extract cache usage from Anthropic response."""
        usage = response.get("usage", {})
        return CacheUsage(
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
        )

    def normalize_response(self, response: Any) -> Dict[str, Any]:
        """Convert Anthropic response to OpenAI-compatible format."""
        return {
            "id": response["id"],
            "object": "chat.completion",
            "model": response["model"],
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response["content"][0]["text"]},
                "finish_reason": response.get("stop_reason", "stop"),
            }],
            "usage": {
                "prompt_tokens": response["usage"]["input_tokens"],
                "completion_tokens": response["usage"]["output_tokens"],
                "total_tokens": response["usage"]["input_tokens"] + response["usage"]["output_tokens"],
            },
        }