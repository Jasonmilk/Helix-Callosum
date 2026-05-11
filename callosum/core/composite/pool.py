"""Backend pool configuration and runtime state (v0.2.0)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from callosum.common.logging import logger


class BackendConfig(BaseModel):
    """Static definition of a backend instance loaded from YAML."""

    name: str
    base_url: str
    adapter: str
    weight: float = Field(1.0, ge=0.0)
    enabled: bool = True


class BackendState(BaseModel):
    """Runtime state of a backend entry, updated by HealthMonitor."""

    config: BackendConfig
    healthy: bool = True
    last_checked: float = Field(default_factory=time.time)
    latency_ms: float = 0.0


class BackendPool:
    """Load backend configurations from YAML and maintain runtime states.

    If the configuration file is absent or contains no backends,
    the pool is empty and Callosum falls back to single-backend mode.
    """

    def __init__(self, config_path: str | Path):
        self._config_path = Path(config_path)
        self._entries: Dict[str, BackendState] = {}

    def load(self) -> None:
        """(Re)load backend definitions from the YAML configuration file."""
        if not self._config_path.exists():
            self._entries.clear()
            return

        raw = self._config_path.read_text(encoding="utf-8").strip()
        if not raw:
            self._entries.clear()
            return

        data = yaml.safe_load(raw) or {}
        backend_list = data.get("backends", [])
        new_entries: Dict[str, BackendState] = {}

        for item in backend_list:
            config = BackendConfig(**item)
            # Preserve existing runtime state when config is unchanged
            old = self._entries.get(config.name)
            if old is not None and old.config == config:
                new_entries[config.name] = old
            else:
                new_entries[config.name] = BackendState(config=config, healthy=config.enabled)

        self._entries = new_entries
        logger.info("Backend pool loaded", count=len(self._entries))

    @property
    def entries(self) -> List[BackendState]:
        """Return all backend states."""
        return list(self._entries.values())

    def get(self, name: str) -> Optional[BackendState]:
        """Return a single backend state by name."""
        return self._entries.get(name)

    def healthy_entries(self) -> List[BackendState]:
        """Return only enabled and currently healthy backends."""
        return [e for e in self._entries.values() if e.config.enabled and e.healthy]

    def update_health(self, name: str, healthy: bool, latency_ms: float = 0.0) -> None:
        """Update the health and latency of a backend after a probe."""
        entry = self._entries.get(name)
        if entry is not None:
            entry.healthy = healthy
            entry.latency_ms = latency_ms
            entry.last_checked = time.time()

    @property
    def is_active(self) -> bool:
        """Return True if the pool contains at least one entry."""
        return len(self._entries) > 0
