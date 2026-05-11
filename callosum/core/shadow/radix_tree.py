"""Token-level path-compressed Radix Tree for prefix cache prediction."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from callosum.common.config import Settings
from callosum.common.utils import compute_sha256


@dataclass
class RadixNode:
    prefix_hash: str
    # The text segment this node represents (for debugging / edge compression)
    edge_text: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    total_access_count: int = 0
    access_timestamps: List[datetime] = field(default_factory=list)
    ttl_seconds: int = 3600
    children: Dict[str, "RadixNode"] = field(default_factory=dict)  # keyed by next token

    @property
    def ttl_remaining(self) -> int:
        """Remaining TTL in seconds for this node."""
        return max(0, self.ttl_seconds - int((datetime.now() - self.last_accessed).total_seconds()))
    
    @property
    def is_expired(self) -> bool:
        """Whether this node has expired."""
        return self.ttl_remaining <= 0


class ShadowRadixTree:
    """Token-level path-compressed Radix Tree for prefix cache prediction.

    Stores token sequences and allows prefix matching (deepest matching node)
    to predict cache hits and self-calibrate TTL values.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.root: RadixNode = RadixNode(prefix_hash="root")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace tokenization for prefix matching."""
        return text.split()

    def lookup(self, prefix_text: str) -> Optional[RadixNode]:
        """Find the deepest node matching the given prefix.

        Args:
            prefix_text: Prefix text to look up.

        Returns:
            Matching RadixNode if found and not expired, None otherwise.
        """
        tokens = self._tokenize(prefix_text)
        node = self.root
        matched_node = None

        for token in tokens:
            if token not in node.children:
                break
            node = node.children[token]
            matched_node = node  # deepest valid node so far

        if matched_node and not matched_node.is_expired:
            # Update access metadata
            matched_node.last_accessed = datetime.now()
            matched_node.access_count += 1
            matched_node.total_access_count += 1
            matched_node.access_timestamps.append(datetime.now())
            return matched_node
        return None

    def insert_or_update(self, prefix_text: str, prefix_hash: str) -> RadixNode:
        """Insert new prefix or update access time of existing node.

        Args:
            prefix_text: Prefix text to insert (for tree navigation).
            prefix_hash: Precomputed prefix hash to store.

        Returns:
            The inserted or updated node.
        """
        tokens = self._tokenize(prefix_text)
        node = self.root

        # Traverse existing tree, creating nodes for missing tokens
        for token in tokens:
            if token not in node.children:
                node.children[token] = RadixNode(
                    prefix_hash=prefix_hash,
                    edge_text=token,
                    ttl_seconds=self.settings.shadow_ttl_initial,
                )
            node = node.children[token]

        # Update the terminal node (represents full prefix)
        node.prefix_hash = prefix_hash  # guarantee the correct hash
        node.last_accessed = datetime.now()
        node.access_count += 1
        node.total_access_count += 1
        node.access_timestamps.append(datetime.now())
        # If the node is expired, extend TTL to initial (re-inserted)
        if node.is_expired:
            node.ttl_seconds = self.settings.shadow_ttl_initial
        return node

    def should_piggyback(self, node: RadixNode) -> bool:
        """Decide whether to refresh this prefix using a piggyback request.

        Args:
            node: The node to check.

        Returns:
            True if a piggyback refresh should be performed, False otherwise.
        """
        # Check if TTL is about to expire
        if node.ttl_remaining < self.settings.shadow_ttl_initial * 0.1:
            # Check if the node is frequently accessed
            if node.access_count > 5:
                # Check if the cost of refresh is acceptable
                return True
        return False

    def update_ttl_from_usage(self, prefix_text: str, actual_ttl: int):
        """Self-calibrate TTL based on actual API behavior.

        Args:
            prefix_text: Prefix text to update.
            actual_ttl: Actual TTL observed from the API.
        """
        tokens = self._tokenize(prefix_text)
        node = self.root
        for token in tokens:
            if token not in node.children:
                # Prefix not found in tree, nothing to update
                return
            node = node.children[token]

        # Update terminal node TTL with weighted average
        alpha = 0.1
        node.ttl_seconds = int((1 - alpha) * node.ttl_seconds + alpha * actual_ttl)