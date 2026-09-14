"""Thread-safe persistent SQLite storage for Brown's Personal & Episodic Memory.

Uses SQLite with WAL mode for ultra-fast (<1ms) concurrent reads and durable atomic writes.
Persists across application restarts.
"""

import os
import time
import json
import sqlite3
import threading
from typing import List, Optional, Dict, Any

from core.memory.base import MemoryRecord, MemoryType


class PersistentMemoryStore:
    """Thread-safe SQLite persistent store for memory records."""

    def __init__(self, db_path: str = "config/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed REAL NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);")
            conn.commit()

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        """Insert or update a memory record by key and type."""
        now = time.time()
        record.updated_at = now
        with self._lock, self._get_connection() as conn:
            # Check if record with same key and type exists
            existing = conn.execute(
                "SELECT id, access_count FROM memories WHERE key = ? AND memory_type = ?",
                (record.key, record.memory_type.value)
            ).fetchone()

            if existing:
                rec_id = existing["id"]
                access_count = existing["access_count"]
                conn.execute("""
                    UPDATE memories
                    SET value = ?, confidence = ?, source = ?, updated_at = ?, metadata_json = ?
                    WHERE id = ?
                """, (
                    record.value,
                    record.confidence,
                    record.source,
                    record.updated_at,
                    json.dumps(record.metadata),
                    rec_id
                ))
                record.id = rec_id
                record.access_count = access_count
            else:
                conn.execute("""
                    INSERT INTO memories (
                        id, memory_type, key, value, confidence, source,
                        created_at, updated_at, access_count, last_accessed, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.memory_type.value,
                    record.key,
                    record.value,
                    record.confidence,
                    record.source,
                    record.created_at,
                    record.updated_at,
                    record.access_count,
                    record.last_accessed,
                    json.dumps(record.metadata)
                ))
            conn.commit()
        return record

    def get(self, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryRecord]:
        """Fetch memory by canonical key."""
        with self._lock, self._get_connection() as conn:
            if memory_type:
                row = conn.execute(
                    "SELECT * FROM memories WHERE key = ? AND memory_type = ? LIMIT 1",
                    (key, memory_type.value)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM memories WHERE key = ? LIMIT 1",
                    (key,)
                ).fetchone()

            if not row:
                return None

            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                (time.time(), row["id"])
            )
            conn.commit()
            return self._row_to_record(row)

    def list(self, memory_type: Optional[MemoryType] = None, limit: int = 50) -> List[MemoryRecord]:
        """List memories optionally filtered by type."""
        with self._lock, self._get_connection() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE memory_type = ? ORDER BY updated_at DESC LIMIT ?",
                    (memory_type.value, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def search(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 5) -> List[MemoryRecord]:
        """Search memories matching keywords in key or value."""
        keywords = [k.strip().lower() for k in query.split() if len(k.strip()) >= 2]
        if not keywords:
            return self.list(memory_type=memory_type, limit=limit)

        with self._lock, self._get_connection() as conn:
            # Build LIKE clauses
            clauses = []
            params = []
            for kw in keywords:
                clauses.append("(LOWER(key) LIKE ? OR LOWER(value) LIKE ?)")
                params.extend([f"%{kw}%", f"%{kw}%"])

            where_str = " OR ".join(clauses)
            if memory_type:
                where_str = f"memory_type = ? AND ({where_str})"
                params.insert(0, memory_type.value)

            sql = f"SELECT * FROM memories WHERE {where_str} ORDER BY confidence DESC, updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(r) for r in rows]

    def delete(self, id: str) -> bool:
        """Delete a memory record by ID."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (id,))
            conn.commit()
            return cur.rowcount > 0

    def delete_by_key(self, key: str, memory_type: Optional[MemoryType] = None) -> bool:
        """Delete a memory record by key."""
        with self._lock, self._get_connection() as conn:
            if memory_type:
                cur = conn.execute("DELETE FROM memories WHERE key = ? AND memory_type = ?", (key, memory_type.value))
            else:
                cur = conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    def clear(self):
        """Purge all stored memories (used in testing)."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM memories;")
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        meta = {}
        try:
            meta = json.loads(row["metadata_json"])
        except Exception:
            pass

        return MemoryRecord(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            metadata=meta
        )
