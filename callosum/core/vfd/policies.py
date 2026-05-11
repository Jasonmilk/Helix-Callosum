"""Pluggable eviction policies for vFD entries."""

from abc import ABC, abstractmethod


class BaseEvictionPolicy(ABC):
    """Abstract base for eviction policies."""
    @abstractmethod
    def compute_score(self, record: dict) -> float:
        """Compute eviction score for a record. Lower score means higher priority to evict."""
        pass


class LRUPolicy(BaseEvictionPolicy):
    """Least Recently Used eviction policy."""
    def compute_score(self, record: dict) -> float:
        return float(record["last_accessed"])


class LFUPolicy(BaseEvictionPolicy):
    """Least Frequently Used eviction policy."""
    def compute_score(self, record: dict) -> float:
        return -float(record["access_frequency"])


class HybridPolicy(BaseEvictionPolicy):
    """Hybrid LRU/LFU eviction policy.
    
    Combines recency and frequency to balance between the two.
    """
    def compute_score(self, record: dict) -> float:
        return float(record["last_accessed"]) / (record["access_frequency"] + 1)
