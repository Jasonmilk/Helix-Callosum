"""Tests for Shadow Tracker."""

import pytest
from callosum.schemas.cache import CacheTrace


def test_shadow_lookup(shadow_tracker):
    """Test shadow tree lookup."""
    # Insert
    trace = CacheTrace(
        hit_predicted=True,
        hit_verified=True,
        prefix_hash="test_prefix",
        saved_tokens_estimated=100,
        saved_tokens_verified=100,
    )
    shadow_tracker.record_cache_interaction(trace)
    
    # Lookup by the same prefix text used in insertion (which is prefix_hash)
    hit = shadow_tracker.predict_hit("test_prefix")
    assert hit is True


def test_stats_aggregation(shadow_tracker):
    """Test statistics aggregation."""
    # Record some hits
    for i in range(10):
        trace = CacheTrace(
            hit_predicted=True,
            hit_verified=True,
            prefix_hash=f"hash_{i}",
            saved_tokens_estimated=100,
            saved_tokens_verified=100,
            saved_cost_usd=0.01,
        )
        shadow_tracker.record_cache_interaction(trace, namespace="test")
    
    # Get stats
    stats = shadow_tracker.get_stats()
    assert stats.total_requests == 10
    assert stats.total_cache_hits == 10
    assert stats.overall_hit_rate == 1.0
    assert stats.total_tokens_saved == 1000
    assert "test" in stats.by_namespace