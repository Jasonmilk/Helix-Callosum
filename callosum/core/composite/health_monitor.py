"""Periodic health check for all backends in the pool (v0.2.0)."""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from callosum.common.config import Settings
from callosum.common.logging import logger
from .pool import BackendPool


class HealthMonitor:
    """Periodically probe each backend and update health status.

    Runs as a background asyncio task. Probe interval and timeout
    are injected from Settings — zero hardcoding.
    """

    def __init__(self, pool: BackendPool, settings: Settings):
        self._pool = pool
        self._interval = settings.health_check_interval
        self._timeout = settings.health_check_timeout
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background monitoring loop (idempotent)."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Health monitor started", interval_s=self._interval)

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Health monitor stopped")

    async def _loop(self) -> None:
        """Main monitoring loop."""
        while True:
            await self._check_all()
            await asyncio.sleep(self._interval)

    async def _check_all(self) -> None:
        """Probe every enabled backend concurrently."""
        for entry in self._pool.entries:
            if not entry.config.enabled:
                continue
            try:
                healthy, latency = await self._probe(entry.config.base_url)
                self._pool.update_health(entry.config.name, healthy, latency)
            except Exception as exc:
                logger.warning(
                    "Health probe failed",
                    backend=entry.config.name,
                    error=str(exc),
                )
                self._pool.update_health(entry.config.name, False)

    async def _probe(self, base_url: str) -> tuple[bool, float]:
        """Perform a lightweight health check against a backend.

        Returns:
            Tuple of (healthy: bool, latency_ms: float).
        """
        loop = asyncio.get_running_loop()
        start = loop.time()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/health")
                latency = (loop.time() - start) * 1000.0
                return resp.status_code == 200, latency
        except Exception:
            latency = (loop.time() - start) * 1000.0
            return False, latency
