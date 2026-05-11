"""Composite routing strategy (v0.2.0)."""

from __future__ import annotations

import random
from typing import Optional

from .pool import BackendPool, BackendState


class CompositeRouter:
    """Select a backend using the configured strategy.

    Supported strategies (configured via CALLOSUM_ROUTING_STRATEGY):
        - first_healthy: Always pick the first healthy backend (stable).
        - round_robin: Cycle through healthy backends evenly.
        - latency_weighted: Weighted random selection based on inverse latency.
    """

    def __init__(self, pool: BackendPool, strategy: str, latency_epsilon_ms: float = 0.001):
        self._pool = pool
        self._strategy = strategy
        self._rr_index: int = 0
        self._latency_epsilon_ms = latency_epsilon_ms

    def select(self) -> Optional[BackendState]:
        """Return the best backend according to the current strategy.

        Returns:
            BackendState if a healthy backend is available, None otherwise.
        """
        healthy = self._pool.healthy_entries()
        if not healthy:
            return None

        if self._strategy == "round_robin":
            return self._select_round_robin(healthy)
        if self._strategy == "latency_weighted":
            return self._select_latency_weighted(healthy)

        # Default: first_healthy — stable ordering, always pick the first
        return healthy[0]

    def _select_round_robin(self, healthy: list[BackendState]) -> BackendState:
        n = len(healthy)
        self._rr_index = self._rr_index % n
        selected = healthy[self._rr_index]
        self._rr_index = (self._rr_index + 1) % n
        return selected

    def _select_latency_weighted(self, healthy: list[BackendState]) -> BackendState:
        """Weighted random selection using inverse latency.

        Delay values are taken from the health monitor; if latency is zero or
        negative, the configured epsilon is used to avoid division by zero.
        """
        weights = []
        for entry in healthy:
            lat = max(entry.latency_ms, self._latency_epsilon_ms)
            weights.append(1.0 / lat)  # lower latency -> higher weight

        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0.0
        for i, entry in enumerate(healthy):
            cumulative += weights[i]
            if r <= cumulative:
                return entry
        # Fallback (should never reach)
        return healthy[-1]
