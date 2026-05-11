"""Tests for Iceberg Compiler."""

import pytest
from callosum.schemas.prompt import PromptBlock, VolatilityLevel


def test_barrier_detection(compiler):
    """Test barrier detection."""
    from callosum.core.iceberg.barrier import detect_barrier, strip_barrier
    
    assert detect_barrier("Hello <callosum-barrier> World") is True
    assert detect_barrier("Hello World") is False
    assert strip_barrier("Hello <callosum-barrier> World") == "Hello  World"


def test_scoring_rules(compiler):
    """Test scoring rules engine."""
    block = PromptBlock(
        content="System prompt",
        role="system",
        volatility=None,
    )
    score = compiler._score_block(block)
    assert score.score == 0
    assert score.reason == "system_prompt"
    
    block = PromptBlock(
        content="User query",
        role="user",
        volatility=None,
    )
    score = compiler._score_block(block)
    assert score.score == 10


def test_dynamic_delimiters(compiler):
    """Test dynamic delimiter generation."""
    # Test with normal content
    content = "Hello world"
    wrapped = compiler._apply_dynamic_delimiters(content)
    assert "<external-data>" in wrapped
    assert "```" in wrapped
    
    # Test with backticks
    content = "```python\nprint('hello')\n```"
    wrapped = compiler._apply_dynamic_delimiters(content)
    # Should use 4 backticks
    assert "````" in wrapped


def test_compile_simple(compiler):
    """Test simple compilation."""
    blocks = [
        PromptBlock(
            content="System prompt",
            role="system",
            volatility=VolatilityLevel(score=0, reason="system"),
        ),
        PromptBlock(
            content="User query",
            role="user",
            volatility=VolatilityLevel(score=10, reason="user"),
        ),
    ]
    
    result = compiler.compile(blocks)
    assert len(result.blocks) == 3  # + attention anchor
    assert result.prefix_hash is not None
    assert result.estimated_savings > 0


def test_compile_with_barrier(compiler):
    """Test compilation with barrier."""
    blocks = [
        PromptBlock(
            content="System prompt",
            role="system",
            volatility=VolatilityLevel(score=0, reason="system"),
        ),
        PromptBlock(
            content="<callosum-barrier>User query",
            role="user",
            volatility=VolatilityLevel(score=10, reason="user"),
            contains_barrier=True,
        ),
    ]
    
    result = compiler.compile(blocks)
    # Protected region should be preserved
    assert result.blocks[-1].content == "User query"