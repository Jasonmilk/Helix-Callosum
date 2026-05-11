"""Tests for composite backend routing (v0.2.0)."""

import pytest
from pathlib import Path

from callosum.core.composite.pool import BackendPool, BackendConfig, BackendState
from callosum.core.composite.router import CompositeRouter


@pytest.fixture
def sample_yaml(tmp_path: Path) -> Path:
    """Create a temporary backends.yaml with two healthy backends."""
    content = """
backends:
  - name: backend-a
    base_url: http://a.example.com:8000
    adapter: openai
    weight: 1.0
    enabled: true
  - name: backend-b
    base_url: http://b.example.com:8000
    adapter: openai
    weight: 1.0
    enabled: true
"""
    path = tmp_path / "backends.yaml"
    path.write_text(content)
    return path


@pytest.fixture
def sample_pool(sample_yaml: Path) -> BackendPool:
    """Create a BackendPool from the sample YAML."""
    pool = BackendPool(sample_yaml)
    pool.load()
    return pool


class TestBackendPool:
    """Unit tests for BackendPool."""

    def test_loads_entries(self, sample_pool):
        """Entries should be loaded from YAML."""
        assert len(sample_pool.entries) == 2
        assert sample_pool.get("backend-a").config.base_url == "http://a.example.com:8000"
        assert sample_pool.get("backend-b").config.adapter == "openai"

    def test_all_healthy_by_default(self, sample_pool):
        """All enabled entries start healthy."""
        assert len(sample_pool.healthy_entries()) == 2

    def test_unhealthy_entry_excluded(self, sample_pool):
        """Marking an entry unhealthy removes it from healthy_entries()."""
        sample_pool.update_health("backend-a", False)
        assert len(sample_pool.healthy_entries()) == 1
        assert sample_pool.healthy_entries()[0].config.name == "backend-b"

    def test_is_active(self, sample_pool):
        """Pool with entries should report as active."""
        assert sample_pool.is_active is True

    def test_empty_pool_not_active(self, tmp_path):
        """Pool with no config file should be inactive."""
        empty_path = tmp_path / "nonexistent.yaml"
        pool = BackendPool(empty_path)
        pool.load()
        assert pool.is_active is False
        assert pool.entries == []


class TestCompositeRouter:
    """Unit tests for CompositeRouter."""

    def test_first_healthy_returns_stable(self, sample_pool):
        """First-healthy strategy always picks the first backend."""
        router = CompositeRouter(sample_pool, "first_healthy")
        for _ in range(3):
            selected = router.select()
            assert selected.config.name == "backend-a"

    def test_round_robin_cycles(self, sample_pool):
        """Round-robin alternates between backends."""
        router = CompositeRouter(sample_pool, "round_robin")
        names = [router.select().config.name for _ in range(4)]
        assert names == ["backend-a", "backend-b", "backend-a", "backend-b"]

    def test_returns_none_when_all_unhealthy(self, sample_pool):
        """Router returns None when no backend is healthy."""
        sample_pool.update_health("backend-a", False)
        sample_pool.update_health("backend-b", False)
        router = CompositeRouter(sample_pool)
        assert router.select() is None

    def test_round_robin_skips_unhealthy(self, sample_pool):
        """Round-robin skips unhealthy backends."""
        sample_pool.update_health("backend-a", False)
        router = CompositeRouter(sample_pool, "round_robin")
        # Should always pick the only healthy one
        for _ in range(3):
            assert router.select().config.name == "backend-b"
