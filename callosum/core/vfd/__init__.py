"""Virtual File Descriptor module for lazy-loading context handles."""

from .allocator import VFDAllocator
from .policies import BaseEvictionPolicy, LRUPolicy, LFUPolicy, HybridPolicy

__all__ = ["VFDAllocator", "BaseEvictionPolicy", "LRUPolicy", "LFUPolicy", "HybridPolicy"]
