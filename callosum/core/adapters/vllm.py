"""vLLM backend adapter."""

import httpx
from typing import Any, Dict, List, Tuple
from callosum.schemas.request import CompiledRequest
from callosum.schemas.cache import CacheUsage, CacheTrace
from callosum.common.config import Settings
from callosum.common.utils import generate_span_id, compute_sha256
from .base import BaseAdapter


class VLLMAdapter(BaseAdapter):
    """Adapter for vLLM backend with automatic prefix caching."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.vllm_base_url.rstrip("/")

    def get_adapter_name(self) -> str:
        return "vllm"

    async def count_tokens(self, text: str) -> int:
        """Count tokens using vLLM's native tokenize API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/tokenize",
                json={"prompt": text},
            )
            resp.raise_for_status()
            return len(resp.json()["tokens"])

    def get_prefix_hash(self, blocks: List) -> str:
        """Compute adapter-specific prefix hash."""
        static_blocks = [b for b in blocks if b.volatility and b.volatility.score <= 1]
        static_text = "".join(b.content for b in static_blocks)
        content_hash = compute_sha256(static_text)
        return f"vllm:{content_hash}"

    async def forward(
        self,
        compiled: CompiledRequest,
        trace_id: str,
        callosum_headers: Dict[str, str] | None = None,
    ) -> Tuple[Any, CacheTrace]:
        """Forward compiled request to vLLM server."""
        headers = {
            "Content-Type": "application/json",
            "traceparent": f"00-{trace_id}-{generate_span_id()}-01",
        }
        if callosum_headers:
            headers.update(callosum_headers)

        messages = [{"role": b.role, "content": b.content} for b in compiled.blocks]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.vllm_model,
                    "messages": messages,
                    "prefix_caching": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        cache_usage = self.extract_cache_usage(data)
        cache_trace = CacheTrace(
            hit_predicted=False,
            hit_verified=False,
            prefix_hash=compiled.prefix_hash,
            saved_tokens_estimated=compiled.estimated_savings,
            saved_tokens_verified=0,
        )
        return data, cache_trace

    async def health_check(self) -> bool:
        """Check if vLLM server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def extract_cache_usage(self, response: Any) -> CacheUsage:
        """vLLM doesn't expose cache usage in standard response yet."""
        return CacheUsage()

    def normalize_response(self, response: Any) -> Dict[str, Any]:
        """vLLM response is already OpenAI-compatible."""
        return response