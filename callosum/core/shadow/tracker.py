"""Shadow tracker for cache hit reconciliation and icebreaker management."""

import asyncio
from typing import Dict, Optional
from pydantic import BaseModel, Field
from callosum.common.config import Settings
from callosum.common.logging import logger
from callosum.schemas.cache import CacheTrace
from .radix_tree import ShadowRadixTree


# Statistics DTOs
class NamespaceStats(BaseModel):
    requests: int
    hit_rate: float
    tokens_saved: int


class ModelStats(BaseModel):
    requests: int
    hit_rate: float
    tokens_saved: int
    avg_ttft_ms: float


class UsageStatsResponse(BaseModel):
    """Response schema for /v1/usage-stats endpoint."""
    total_requests: int
    total_cache_hits: int
    total_cache_misses: int
    overall_hit_rate: float
    total_tokens_saved: int
    total_cost_saved_usd: float
    by_namespace: Dict[str, NamespaceStats] = Field(default_factory=dict)
    by_model: Dict[str, ModelStats] = Field(default_factory=dict)


class IcebreakerManager:
    """Manage icebreaker requests to prevent thundering herd on cache miss.

    Ensures only one request probes the cache for a missing prefix,
    while others wait, preventing thundering herd.
    """

    def __init__(self, settings: Settings):
        self.max_wait_ms = settings.icebreaker_max_wait_ms
        self.ttft_threshold_ms = settings.icebreaker_ttft_threshold_ms
        self._active_probes: Dict[str, asyncio.Event] = {}

    async def wait_or_probe(self, prefix_hash: str) -> bool:
        """Wait for existing probe or become the probe.

        Returns True if the caller should proceed as the probe,
        False if it was released by a completed probe.
        """
        existing = self._active_probes.get(prefix_hash)
        if existing:
            # Wait for the existing probe with timeout
            try:
                await asyncio.wait_for(existing.wait(), timeout=self.max_wait_ms / 1000)
                return False
            except asyncio.TimeoutError:
                # Previous probe timed out, we become the new probe
                logger.warning(
                    "Icebreaker probe timed out, starting new probe", 
                    prefix_hash=prefix_hash
                )
        
        # Create new probe
        event = asyncio.Event()
        self._active_probes[prefix_hash] = event
        return True

    def complete_probe(self, prefix_hash: str):
        """Mark a probe as completed and release waiting tasks."""
        event = self._active_probes.pop(prefix_hash, None)
        if event:
            event.set()


class ShadowTracker:
    """Track cache hits, update shadow tree, and manage icebreaker requests.

    Aggregates cache performance statistics and updates the shadow radix tree
    based on actual API responses.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._radix_tree = ShadowRadixTree(settings)
        self._icebreaker = IcebreakerManager(settings)
        
        # Aggregated statistics
        self._total_requests: int = 0
        self._total_cache_hits: int = 0
        self._total_cache_misses: int = 0
        self._total_tokens_saved: int = 0
        self._total_cost_saved: float = 0.0
        self._by_namespace: Dict[str, dict] = {}
        self._by_model: Dict[str, dict] = {}

    def predict_hit(self, prefix_text: str) -> bool:
        """Predict if a prefix will hit the cache.

        Args:
            prefix_text: Prefix text to check.

        Returns:
            True if hit is predicted, False otherwise.
        """
        node = self._radix_tree.lookup(prefix_text)
        return node is not None

    async def wait_for_icebreaker(self, prefix_hash: str) -> bool:
        """Wait for icebreaker probe if needed.

        Args:
            prefix_hash: Prefix hash to check.

        Returns:
            True if caller should be the probe, False otherwise.
        """
        return await self._icebreaker.wait_or_probe(prefix_hash)

    def complete_icebreaker(self, prefix_hash: str):
        """Complete an icebreaker probe and release waiting tasks."""
        self._icebreaker.complete_probe(prefix_hash)

    def record_cache_interaction(
        self, 
        trace: CacheTrace, 
        namespace: str = "default", 
        model_id: str = "default"
    ):
        """Record a cache interaction for statistics and shadow tree update.

        Args:
            trace: CacheTrace object from the backend interaction.
            namespace: Sandbox namespace for isolation.
            model_id: Backend model identifier.
        """
        # Update global statistics
        self._total_requests += 1
        if trace.hit_verified:
            self._total_cache_hits += 1
            self._total_tokens_saved += trace.saved_tokens_verified or 0
            self._total_cost_saved += trace.saved_cost_usd
        else:
            self._total_cache_misses += 1
        
        # Update namespace statistics
        ns = namespace or "default"
        if ns not in self._by_namespace:
            self._by_namespace[ns] = {"requests": 0, "hits": 0, "tokens_saved": 0}
        self._by_namespace[ns]["requests"] += 1
        if trace.hit_verified:
            self._by_namespace[ns]["hits"] += 1
            self._by_namespace[ns]["tokens_saved"] += trace.saved_tokens_verified or 0
        
        # Update model statistics
        mid = model_id or "default"
        if mid not in self._by_model:
            self._by_model[mid] = {"requests": 0, "hits": 0, "tokens_saved": 0, "ttft_sum": 0.0}
        self._by_model[mid]["requests"] += 1
        if trace.hit_verified:
            self._by_model[mid]["hits"] += 1
            self._by_model[mid]["tokens_saved"] += trace.saved_tokens_verified or 0
        
        # Update shadow tree
        # Insert the prefix hash along with a representative text (for tree navigation).
        # Since we only have prefix_hash here, we use it as both text and hash.
        # In a complete implementation, prefix_text would come from the adapter.
        self._radix_tree.insert_or_update(trace.prefix_hash, trace.prefix_hash)

    def get_stats(self, namespace: str = None, model_id: str = None) -> UsageStatsResponse:
        """Return cache performance statistics, optionally filtered.

        Args:
            namespace: Optional sandbox namespace filter.
            model_id: Optional model identifier filter.

        Returns:
            UsageStatsResponse with aggregated cache metrics.
        """
        total_requests = self._total_requests
        total_hits = self._total_cache_hits
        total_misses = self._total_cache_misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0
        
        # Build namespace statistics
        by_namespace = {}
        for ns, data in self._by_namespace.items():
            if namespace and ns != namespace:
                continue
            reqs = data["requests"]
            hits = data["hits"]
            by_namespace[ns] = NamespaceStats(
                requests=reqs,
                hit_rate=hits / reqs if reqs > 0 else 0.0,
                tokens_saved=data["tokens_saved"],
            )
        
        # Build model statistics
        by_model = {}
        for mid, data in self._by_model.items():
            if model_id and mid != model_id:
                continue
            reqs = data["requests"]
            hits = data["hits"]
            by_model[mid] = ModelStats(
                requests=reqs,
                hit_rate=hits / reqs if reqs > 0 else 0.0,
                tokens_saved=data["tokens_saved"],
                avg_ttft_ms=data.get("ttft_sum", 0.0) / reqs if reqs > 0 else 0.0,
            )
        
        return UsageStatsResponse(
            total_requests=total_requests,
            total_cache_hits=total_hits,
            total_cache_misses=total_misses,
            overall_hit_rate=overall_hit_rate,
            total_tokens_saved=self._total_tokens_saved,
            total_cost_saved_usd=self._total_cost_saved,
            by_namespace=by_namespace,
            by_model=by_model,
        )