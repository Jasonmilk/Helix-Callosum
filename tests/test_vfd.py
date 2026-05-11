"""Tests for vFD Allocator."""

import pytest
import tempfile
import os


@pytest.mark.asyncio
async def test_vfd_resolve(vfd_allocator):
    """Test vFD handle resolution."""
    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Test content")
        temp_path = f.name
    
    try:
        handle = f"{{@ref:{temp_path}}}"
        content = await vfd_allocator.resolve(handle)
        assert content == "Test content"
        
        # Check index
        entry = await vfd_allocator._indexer.get(handle)
        assert entry is not None
        assert entry["content_hash"] is not None
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_vfd_eviction(vfd_allocator, settings):
    """Test eviction policy."""
    # Fill the index
    settings.lru_max_size = 2
    
    for i in range(5):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write(f"Content {i}")
            temp_path = f.name
        
        handle = f"{{@ref:{temp_path}}}"
        await vfd_allocator.resolve(handle)
        os.unlink(temp_path)
    
    # Trigger eviction
    await vfd_allocator.evict_lru_if_needed()
    
    # Should have at most 2 entries
    count = await vfd_allocator._indexer.count()
    assert count <= 2