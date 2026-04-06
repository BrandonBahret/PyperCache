"""High-performance SQLite cache storage backend.

IO Strategy — Write-Behind Buffer
──────────────────────────────────
The dominant cost in the naive SQLite backend is per-write fsync: every
``commit()`` forces the OS to flush pages to disk.  For large JSON/HTML
records this is the single biggest latency killer.

This backend eliminates that by:

1. **Hot read cache** — all records are loaded into memory on open.
   ``get_record`` never touches disk (O(1) dict lookup).

2. **Write-behind dirty buffer** — ``store_record`` / ``update_record``
   write into the in-memory dict *and* mark the key dirty.  No disk IO at
   all until a flush is triggered.

3. **Batch flush** — dirty keys are persisted in a *single* transaction
   (one fsync regardless of how many records changed).  Flush is triggered
   by any of:
     a. ``DIRTY_FLUSH_THRESHOLD`` dirty keys accumulated (default 50)
     b. ``FLUSH_INTERVAL_SECONDS`` wall-clock seconds elapsed (default 5 s)
        — a background daemon thread handles this automatically.
     c. Explicit ``flush()`` call.
     d. ``close()`` / context-manager ``__exit__``.

4. **Single-commit bulk upsert** — the flush uses ``executemany`` inside
   one ``BEGIN … COMMIT`` block, so N dirty records → 1 fsync.

5. **WAL mode** — concurrent readers are never blocked by the writer.

Schema
──────
Each cache record is stored with its fields in dedicated columns rather
than a single serialised JSON blob:

    key        TEXT PRIMARY KEY
    cast       TEXT             — type/cast metadata
    expiry     REAL             — expiry timestamp (Unix epoch, nullable)
    timestamp  REAL             — record creation/update time (Unix epoch)
    data       BLOB             — raw payload bytes (JSON, msgpack-prefixed, or raw BLOB)

Trade-off: a process crash between flushes can lose at most
``FLUSH_INTERVAL_SECONDS`` seconds of writes.  For a *cache* this is
always acceptable — stale-miss on restart is far cheaper than per-write
fsync latency under load.
"""

import json
import jsonpickle
import msgpack
import sqlite3
import threading
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Dict, Iterator, Optional, Set

from PyperCache.storage.base import StorageMechanism
from PyperCache.utils.fs import ensure_dirs_exist


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

DIRTY_FLUSH_THRESHOLD: int = 50      # flush when this many keys are dirty
FLUSH_INTERVAL_SECONDS: float = 5.0  # background flush cadence in seconds

# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

# Canonical field names that map to dedicated columns.
_COLUMNS = ("cast", "expiry", "timestamp", "data")

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS cache_records (
        key        TEXT PRIMARY KEY,
        "cast"     TEXT,
        expiry     REAL,
        timestamp  REAL,
        data       BLOB
    )
"""

_UPSERT = """
    INSERT INTO cache_records (key, "cast", expiry, timestamp, data)
         VALUES (:key, :cast, :expiry, :timestamp, :data)
    ON CONFLICT(key) DO UPDATE SET
        "cast"    = excluded."cast",
        expiry    = excluded.expiry,
        timestamp = excluded.timestamp,
        data      = excluded.data
"""

_SELECT_ALL = """SELECT key, "cast", expiry, timestamp, data FROM cache_records"""
_DELETE_KEY = "DELETE FROM cache_records WHERE key = ?"


_MSGPACK_PREFIX     = b'\x00'  # null byte never appears at the start of valid JSON
_JSONPICKLE_PREFIX  = b'\x01'  # SOH byte — fallback for types msgpack can't handle


def _serialize_data(value) -> Optional[bytes]:
    """Encode the ``data`` field to bytes for SQLite BLOB storage.

    Encoding ladder (first success wins):
    - ``None``       → NULL in DB
    - ``bytes``      → raw BLOB as-is
    - JSON-able      → plain UTF-8 JSON text
    - msgpack-able   → ``\\x00`` + msgpack bytes  (e.g. dicts containing bytes)
    - anything else  → ``\\x01`` + jsonpickle JSON (arbitrary Python objects)
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)  # pure bytes → BLOB as-is
    try:
        return json.dumps(value).encode()  # plain JSON for normal data
    except (TypeError, ValueError):
        pass
    try:
        return _MSGPACK_PREFIX + msgpack.dumps(value)  # dicts containing bytes etc.
    except Exception:
        pass
    return _JSONPICKLE_PREFIX + jsonpickle.encode(value).encode()  # arbitrary objects


def _deserialize_data(raw) -> object:
    """Decode bytes retrieved from the BLOB column back to a Python object.

    - ``None``            → ``None``
    - ``\\x00`` prefix    → msgpack decode
    - ``\\x01`` prefix    → jsonpickle decode
    - valid UTF-8 JSON    → parsed object
    - non-JSON bytes      → returned as raw ``bytes``
    """
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        if raw.startswith(_MSGPACK_PREFIX):
            return msgpack.loads(memoryview(raw)[1:], raw=False)
        if raw.startswith(_JSONPICKLE_PREFIX):
            return jsonpickle.decode(memoryview(raw)[1:].tobytes().decode())
        try:
            return json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return bytes(raw)  # pure BLOB fallback
    # SQLite may return a str if the column affinity kicked in
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def _row_to_record(row: tuple) -> dict:
    """Convert a ``(key, cast, expiry, timestamp, data)`` DB row to a dict."""
    _key, cast, expiry, timestamp, raw_data = row
    return {
        "cast": cast,
        "expiry": expiry,
        "timestamp": timestamp,
        "data": _deserialize_data(raw_data),
    }


def _record_to_params(key: str, record: dict) -> dict:
    """Convert an in-memory record dict to named params for :data:`_UPSERT`."""
    return {
        "key": key,
        "cast": record.get("cast"),
        "expiry": record.get("expiry"),
        "timestamp": record.get("timestamp"),
        "data": _serialize_data(record.get("data")),
    }


# ---------------------------------------------------------------------------
# In-memory MutableMapping with dirty tracking
# ---------------------------------------------------------------------------

class _BufferedMapping(MutableMapping):
    """In-memory ``dict`` with a dirty-key set for write-behind flushing.

    All reads are served from ``_store`` (pure RAM, zero IO).
    All writes update ``_store`` and mark the key in ``_dirty``.

    The owning :class:`SQLiteStorage` inspects ``_dirty`` and calls
    :meth:`pop_dirty` to drain it during a flush.
    """

    def __init__(self, initial: Dict[str, dict]):
        self._store: Dict[str, dict] = initial
        self._dirty: Set[str] = set()
        self._deleted: Set[str] = set()

    # MutableMapping protocol --------------------------------------------------

    def __getitem__(self, key: str) -> dict:
        return self._store[key]           # pure RAM — zero IO

    def __setitem__(self, key: str, value: dict):
        self._store[key] = value
        self._dirty.add(key)
        self._deleted.discard(key)        # un-delete if re-inserted

    def __delitem__(self, key: str):
        if key not in self._store:
            raise KeyError(key)
        del self._store[key]
        self._dirty.discard(key)
        self._deleted.add(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)          # pure RAM

    def __len__(self) -> int:
        return len(self._store)           # pure RAM

    def __contains__(self, key: object) -> bool:
        return key in self._store         # pure RAM

    # Dirty-buffer helpers -----------------------------------------------------

    @property
    def dirty_count(self) -> int:
        return len(self._dirty)

    def pop_dirty(self) -> tuple[Dict[str, dict], Set[str]]:
        """Return pending upserts and deletes, then clear both sets."""
        upserts = {k: self._store[k] for k in self._dirty if k in self._store}
        deletes = set(self._deleted)
        self._dirty.clear()
        self._deleted.clear()
        return upserts, deletes


# ---------------------------------------------------------------------------
# StorageMechanism implementation
# ---------------------------------------------------------------------------

class SQLiteStorage(StorageMechanism):
    """Cache storage backend with a write-behind buffer over SQLite.

    Reads are always served from RAM (after a one-time bulk load on open).
    Writes accumulate in a dirty buffer and are flushed to disk in a single
    batched transaction, collapsing N fsyncs into 1.

    Each cache record is stored in a typed, columnar schema::

        key        TEXT PRIMARY KEY
        cast       TEXT
        expiry     REAL   (Unix epoch float, nullable)
        timestamp  REAL   (Unix epoch float)
        data       BLOB

    Usage::

        # Recommended: use as a context manager so close() always runs.
        with SQLiteStorage("path/to/cache.db") as store:
            store.store_record("page-1", {
                "cast": "html",
                "expiry": 1700000000.0,
                "timestamp": 1699990000.0,
                "data": b"<p>...</p>",
            })
            record = store.get_record("page-1")

        # Manual lifecycle:
        store = SQLiteStorage("cache.db")
        store.store_record("k", {"cast": "json", "timestamp": time.time(), "data": b"{}"})
        store.flush()   # explicit flush without closing
        store.close()   # flushes + closes connection

    Args:
        filepath: Path to the ``.db`` file.  Created automatically.
        flush_interval: Seconds between background auto-flushes (default 5 s).
        dirty_threshold: Flush immediately when this many keys are dirty
                         (default 50).
    """

    _TABLE = "cache_records"

    def __init__(
        self,
        filepath: str,
        flush_interval: float = FLUSH_INTERVAL_SECONDS,
        dirty_threshold: int = DIRTY_FLUSH_THRESHOLD,
    ):
        self._conn: sqlite3.Connection | None = None
        self._flush_interval = flush_interval
        self._dirty_threshold = dirty_threshold
        self._flush_lock = threading.Lock()   # serialises actual DB writes
        self._closed = False

        # super().__init__ calls load() which opens the connection and
        # populates self.records with a _BufferedMapping.
        super().__init__(filepath)

        # Start background flush thread after records are ready.
        self._bg_thread = threading.Thread(
            target=self._background_flush_loop,
            daemon=True,
            name=f"SQLiteStorage-flush-{filepath}",
        )
        self._bg_thread.start()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _open_connection(self, filepath: Path) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(filepath),
                check_same_thread=False,  # serialised by _flush_lock + base lock
                isolation_level=None,     # we manage transactions manually
            )
            # WAL: readers never block writers; writers never block readers.
            self._conn.execute("PRAGMA journal_mode=WAL")
            # Larger pages suit big binary blobs.
            self._conn.execute("PRAGMA page_size=8192")
            # OS handles durability — we don't need per-commit fsync.
            self._conn.execute("PRAGMA synchronous=NORMAL")
            # 64 MB shared-memory cache — reduces repeated page reads.
            self._conn.execute("PRAGMA cache_size=-65536")
        return self._conn

    # ------------------------------------------------------------------
    # Background flush loop
    # ------------------------------------------------------------------

    def _background_flush_loop(self):
        """Daemon thread: flush dirty buffer every ``_flush_interval`` seconds."""
        while not self._closed:
            time.sleep(self._flush_interval)
            if not self._closed:
                self._do_flush()

    # ------------------------------------------------------------------
    # Flush logic
    # ------------------------------------------------------------------

    def _do_flush(self):
        """Write all dirty records to SQLite in one transaction (one fsync)."""
        if not isinstance(self.records, _BufferedMapping):
            return
        if self.records.dirty_count == 0 and not self.records._deleted:
            return

        with self._flush_lock:
            upserts, deletes = self.records.pop_dirty()

            if not upserts and not deletes:
                return

            conn = self._conn
            if conn is None:
                return

            try:
                conn.execute("BEGIN")

                if upserts:
                    conn.executemany(
                        _UPSERT,
                        (_record_to_params(k, v) for k, v in upserts.items()),
                    )

                if deletes:
                    conn.executemany(
                        _DELETE_KEY,
                        ((k,) for k in deletes),
                    )

                conn.execute("COMMIT")   # one fsync for all dirty records
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise

    def flush(self):
        """Public API: force an immediate flush of the dirty buffer."""
        self._do_flush()

    def _maybe_flush(self):
        """Flush eagerly if the dirty buffer has hit the threshold."""
        if (
            isinstance(self.records, _BufferedMapping)
            and self.records.dirty_count >= self._dirty_threshold
        ):
            self._do_flush()

    # ------------------------------------------------------------------
    # StorageMechanism public API overrides
    # ------------------------------------------------------------------

    def store_record(self, key: str, cache_record_dict: dict):
        """Insert or overwrite *key* in the in-memory buffer and mark dirty.

        Overrides the base class to skip the synchronous ``save()`` call that
        would otherwise acquire the lock and call ``touch_store()`` on every
        write.  Persistence is handled lazily by the dirty-buffer flush cycle.
        """
        self.records[str(key)] = cache_record_dict   # __setitem__ marks dirty
        self._maybe_flush()                          # flush only if threshold hit

    # ------------------------------------------------------------------
    # StorageMechanism abstract hooks
    # ------------------------------------------------------------------

    def _impl__touch_store(self, filepath: Path) -> bool:
        """Create the SQLite file and records table if absent."""
        try:
            conn = self._open_connection(filepath)
            conn.execute(_CREATE_TABLE)
            conn.commit()
            return True
        except sqlite3.Error:
            return False

    def _impl__load(self, filepath: Path) -> MutableMapping[str, dict]:
        """Bulk-load every record from disk into a :class:`_BufferedMapping`.

        This is the only full-table scan that ever happens.  After this
        point all reads are served from RAM.  Each row is unpacked into a
        plain dict with keys ``cast``, ``expiry``, ``timestamp``, ``data``.
        """
        conn = self._open_connection(filepath)
        rows = conn.execute(_SELECT_ALL).fetchall()
        initial = {row[0]: _row_to_record(row) for row in rows}
        return _BufferedMapping(initial)

    def _impl__save(self, cache_records_dict: Dict[str, dict], filepath: Path):
        """Called by the base class after store_record; threshold-check only."""
        self._maybe_flush()

    def _impl__update_record(self, key: str, data: dict):
        """Merge *data* into the existing record (pure RAM) and mark dirty.

        Only the four recognised columns (``cast``, ``expiry``, ``timestamp``,
        ``data``) are merged; unknown keys in *data* are ignored so that
        callers cannot accidentally introduce columns that do not exist in
        the schema.
        """
        existing = self.records.get(key, {})
        for col in _COLUMNS:
            if col in data:
                existing[col] = data[col]
        self.records[key] = existing      # __setitem__ marks dirty — no IO

    def _impl__erase_everything(self):
        """Clear the in-memory buffer and the on-disk table atomically."""
        with self._flush_lock:
            if isinstance(self.records, _BufferedMapping):
                self.records._dirty.clear()
                self.records._deleted.clear()
                self.records._store.clear()
            if self._conn:
                self._conn.execute("BEGIN")
                self._conn.execute(f"DELETE FROM {self._TABLE}")
                self._conn.execute("COMMIT")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Flush all dirty records, then close the SQLite connection.

        Always call this (or use the context manager) so pending writes
        are not lost when the process exits.
        """
        self._closed = True
        self._do_flush()             # final flush — nothing left behind
        if self._conn:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()