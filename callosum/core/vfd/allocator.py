"""vFD Allocator main implementation."""

import time
import importlib
from typing import List, Set
from callosum.common.config import Settings
from callosum.common.logging import logger
from callosum.common.utils import compute_sha256
from callosum.schemas.exceptions import VFDResolutionError
from .indexer import VFDIndexer


class VFDAllocator:
    """Manage virtual file descriptor lifecycle.

    Resolves vFD handles to file content, maintains SQLite index,
    and performs eviction at request boundaries to prevent memory bloat.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._indexer = VFDIndexer(settings.vfd_index_path)
        self._locked_handles: Set[str] = set()
        self._eviction_policy = self._load_policy()

    def _load_policy(self):
        """Load eviction policy class by name from settings. Zero hardcoding."""
        policy_name = self.settings.eviction_policy.lower()
        # Map policy names to full class paths
        policy_map = {
            "lru": ".policies.LRUPolicy",
            "lfu": ".policies.LFUPolicy",
            "hybrid": ".policies.HybridPolicy",
        }
        if policy_name not in policy_map:
            logger.warning("Unknown eviction policy, falling back to hybrid", policy=policy_name)
            policy_name = "hybrid"

        class_path = policy_map[policy_name]
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path, package="callosum.core.vfd")
        policy_cls = getattr(module, class_name)
        return policy_cls()

    async def resolve(self, handle: str) -> str:
        """Expand a vFD handle to its current file content.

        Args:
            handle: vFD handle in format {@ref:path}.

        Returns:
            File content as string.

        Raises:
            VFDResolutionError: If the handle cannot be resolved.
        """
        # Parse handle format
        if not handle.startswith("{@ref:") or not handle.endswith("}"):
            raise VFDResolutionError(f"Invalid vFD handle format: {handle}")
        
        file_path = handle[6:-1].strip()
        
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Compute content hash for change detection
            content_hash = compute_sha256(content)
            size_bytes = len(content.encode("utf-8"))
            
            # Update index
            existing = await self._indexer.get(handle)
            if existing:
                if existing["content_hash"] != content_hash:
                    # Content has changed, replace the entry
                    await self._indexer.insert(handle, content_hash, file_path, size_bytes)
                    logger.debug("Updated vFD entry (content changed)", handle=handle)
                else:
                    # Content unchanged, just update access time
                    await self._indexer.touch(handle)
            else:
                # New entry, insert into index
                await self._indexer.insert(handle, content_hash, file_path, size_bytes)
                logger.debug("Added new vFD entry", handle=handle)
            
            return content
        except Exception as e:
            logger.error("Failed to resolve vFD handle", handle=handle, error=str(e))
            raise VFDResolutionError(f"Failed to resolve vFD handle {handle}: {e}")

    def lock_generation(self, handles: List[str]) -> None:
        """Lock handles for the duration of one request generation.

        Locked handles will not be evicted during this request to prevent
        interruption of autoregressive generation.

        Args:
            handles: List of handles to lock.
        """
        self._locked_handles = set(handles)
        logger.debug("Locked generation handles", handles=handles)

    def unlock_generation(self) -> None:
        """Release all generation locks.
        
        Called at the end of a request to allow eviction of previously locked entries.
        """
        count = len(self._locked_handles)
        self._locked_handles.clear()
        logger.debug("Unlocked generation handles", count=count)

    async def evict_lru_if_needed(self) -> None:
        """Perform eviction at request boundary using the configured policy.

        Only evicts entries that are not currently locked by an active generation.
        This ensures we never evict content that's being used by an in-flight request.
        """
        current_count = await self._indexer.count()
        max_size = self.settings.lru_max_size
        
        if current_count <= max_size:
            return
        
        # Need to evict entries to stay under the limit
        to_evict = current_count - max_size
        logger.info(
            "Performing vFD eviction", 
            current_count=current_count, 
            max_size=max_size, 
            to_evict=to_evict
        )
        
        # Get candidates for eviction
        candidates = await self._indexer.get_candidates_for_eviction(limit=to_evict + 10)
        
        # Sort candidates by policy score (lower = evict first)
        candidates.sort(key=lambda r: self._eviction_policy.compute_score(r))
        
        # Evict unlocked candidates
        evicted = 0
        for candidate in candidates:
            if evicted >= to_evict:
                break
            
            handle = candidate["handle"]
            if handle in self._locked_handles:
                logger.debug("Skipping locked vFD entry for eviction", handle=handle)
                continue  # Skip entries locked by active generation
            
            await self._indexer.delete(handle)
            evicted += 1
            logger.debug("Evicted vFD entry", handle=handle)
        
        logger.info("vFD eviction complete", evicted_count=evicted)