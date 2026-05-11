"""SQLite hash index for vFD entries with WAL mode."""

import time
import aiosqlite
from pathlib import Path
from typing import List, Optional, Dict
from callosum.common.logging import logger


class VFDIndexer:
    """SQLite hash index for vFD entries (WAL mode)."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._initialized = False

    async def _init_db(self):
        """Initialize WAL mode and schema if not already initialized."""
        if self._initialized:
            return
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrency and performance
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            
            # Create main table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vfd_index (
                    handle TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    last_accessed INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    access_frequency INTEGER DEFAULT 1,
                    size_bytes INTEGER
                )
            """)
            
            # Create indexes for fast lookups
            await db.execute("CREATE INDEX IF NOT EXISTS idx_hash ON vfd_index(content_hash)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON vfd_index(last_accessed)")
            
            await db.commit()
        
        self._initialized = True
        logger.info("vFD index initialized", db_path=str(self.db_path))

    async def get(self, handle: str) -> Optional[dict]:
        """Get a vFD entry by handle.
        
        Args:
            handle: vFD handle to look up.
            
        Returns:
            Entry dictionary if found, None otherwise.
        """
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM vfd_index WHERE handle = ?", (handle,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def insert(self, handle: str, content_hash: str, file_path: str, size_bytes: int):
        """Insert a new vFD entry.
        
        Args:
            handle: vFD handle.
            content_hash: SHA256 hash of the file content.
            file_path: Path to the original file.
            size_bytes: Size of the content in bytes.
        """
        await self._init_db()
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO vfd_index 
                (handle, content_hash, file_path, last_accessed, size_bytes)
                VALUES (?, ?, ?, ?, ?)
            """, (handle, content_hash, file_path, now, size_bytes))
            await db.commit()

    async def update(self, handle: str, **kwargs):
        """Update fields of an existing vFD entry.
        
        Args:
            handle: vFD handle to update.
            **kwargs: Key-value pairs to update.
        """
        await self._init_db()
        if not kwargs:
            return
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [handle]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE vfd_index SET {set_clause} WHERE handle = ?", values)
            await db.commit()

    async def touch(self, handle: str):
        """Update last_accessed time and increment access count.
        
        Args:
            handle: vFD handle to touch.
        """
        await self._init_db()
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE vfd_index 
                SET last_accessed = ?, access_count = access_count + 1
                WHERE handle = ?
            """, (now, handle))
            await db.commit()

    async def count(self) -> int:
        """Count total number of entries in the index.
        
        Returns:
            Total entry count.
        """
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM vfd_index") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_candidates_for_eviction(self, limit: int) -> List[dict]:
        """Get candidates for eviction, ordered by last accessed time.
        
        Args:
            limit: Maximum number of candidates to return.
            
        Returns:
            List of candidate entries.
        """
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM vfd_index 
                ORDER BY last_accessed ASC 
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete(self, handle: str):
        """Delete a vFD entry from the index.
        
        Args:
            handle: vFD handle to delete.
        """
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM vfd_index WHERE handle = ?", (handle,))
            await db.commit()
