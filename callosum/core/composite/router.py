"""Composite routing strategy (v0.2.0)."""

from __future__ import annotations

from typing import Optional

from .pool import BackendPool, BackendState


class CompositeRouter:
    """Select a backend using the configured strategy.

    Supported strategies (configured via CALLOSUM_ROUTING_STRATEGY):
        - first_healthy: Always pick the first healthy backend (stable).
        - round_robin: Cycle through healthy backends evenly.
    """

    def __init__(self, pool: BackendPool, strategy: str = "first_healthy"):
        self._pool = pool
        self._strategy = strategy
        self._rr_index: int = 0

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

        # Default: first_healthy — stable ordering, always pick the first
        return healthy[0]

    def _select_round_robin(self, healthy: list[BackendState]) -> BackendState:
        """Cycle through healthy backends in round-robin order."""
        n = len(healthy)
        self._rr_index = self._rr_index % n
        selected = healthy[self._rr_index]
        self._rr_index = (self._rr_index + 1) % n
        return selected
