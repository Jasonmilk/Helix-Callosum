"""Tests for Economic Profiler."""

import pytest
from callosum.schemas.prompt import PromptBlock, VolatilityLevel


def test_should_reorder_small_prompt(economic_profiler):
    """Test that small prompts skip reordering."""
    blocks = [
        PromptBlock(
            content="System",
            role="system",
            volatility=VolatilityLevel(score=0, reason="system"),
        ),
        PromptBlock(
            content="User",
            role="user",
            volatility=VolatilityLevel(score=10, reason="user"),
        ),
    ]
    
    should_reorder, savings = economic_profiler.should_reorder(blocks, 100)
    assert should_reorder is False


def test_should_reorder_with_barrier(economic_profiler):
    """Test that barrier permits reordering."""
    blocks = [
        PromptBlock(
            content="System",
            role="system",
            volatility=VolatilityLevel(score=0, reason="system"),
        ),
        PromptBlock(
            content="User",
            role="user",
            volatility=VolatilityLevel(score=10, reason="user"),
            contains_barrier=True,
        ),
    ]
    
    should_reorder, savings = economic_profiler.should_reorder(blocks, 10000)
    assert should_reorder is True


def test_threshold_update(economic_profiler):
    """Test threshold self-calibration."""
    initial = economic_profiler._threshold
    economic_profiler.update_thresholds(0.8, 500)
    assert economic_profiler._threshold != initial
    # Should be clamped
    assert economic_profiler._threshold >= economic_profiler.settings.min_savings_threshold
    assert economic_profiler._threshold <= economic_profiler.settings.max_savings_threshold