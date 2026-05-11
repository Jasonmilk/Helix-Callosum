"""Pytest configuration."""

import pytest
from callosum.common.config import Settings, get_settings
from callosum.core.iceberg import IcebergCompiler
from callosum.core.vfd import VFDAllocator
from callosum.core.economic import EconomicProfiler
from callosum.core.shadow import ShadowTracker


@pytest.fixture
def settings():
    """Test settings fixture."""
    return get_settings()


@pytest.fixture
def compiler(settings):
    """Iceberg compiler fixture."""
    return IcebergCompiler(settings)


@pytest.fixture
def vfd_allocator(settings):
    """vFD allocator fixture."""
    return VFDAllocator(settings)


@pytest.fixture
def economic_profiler(settings):
    """Economic profiler fixture."""
    return EconomicProfiler(settings)


@pytest.fixture
def shadow_tracker(settings):
    """Shadow tracker fixture."""
    return ShadowTracker(settings)