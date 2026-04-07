"""Tests and performance benchmarks for SQLiteStorage.

Run all tests:
    pytest test_sqlite_storage.py -v

Run only benchmarks (with timing output):
    pytest test_sqlite_storage.py -v -k "bench" -s

Run only correctness tests:
    pytest test_sqlite_storage.py -v -k "not bench"
"""

import math
import sqlite3
import time
import threading
from pathlib import Path

import pytest

from pypercache import CacheRecord
from pypercache.storage.sqlite_storage import (
    SQLiteStorage,
    _BufferedMapping,
    _serialize_data,
    _deserialize_data,
    _row_to_record,
    DIRTY_FLUSH_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(data=None, expiry=math.inf, cast=None) -> dict:
    """Build a raw record dict via CacheRecord.from_data() then as_dict().

    StorageMechanism.store_record() expects a plain dict (it wraps it in
    CacheRecord on the way out via get_record).  Passing a CacheRecord
    instance directly causes a double-wrap TypeError.
    """
    return CacheRecord.from_data(
        data=data or {"value": 1},
        expiry=expiry,
        cast=cast,
    ).as_dict()


def record_count_on_disk(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM cache_records").fetchone()[0]
    conn.close()
    return count


def read_row_from_disk(db_path: Path, key: str) -> dict | None:
    """Return the raw column dict for a key, bypassing the in-memory cache."""
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        'SELECT key, "cast", expiry, timestamp, data FROM cache_records WHERE key = ?',
        (key,),
    ).fetchone()
    conn.close()
    return _row_to_record(row) if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def store(db_path):
    """Open a SQLiteStorage with background flush disabled, yield it, close it."""
    s = SQLiteStorage(
        str(db_path),
        flush_interval=60.0,       # disable background flush during tests
        dirty_threshold=DIRTY_FLUSH_THRESHOLD,
    )
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Unit tests — serialisation helpers
# ---------------------------------------------------------------------------

class TestSerialisation:
    def test_serialize_none(self):
        assert _serialize_data(None) is None

    def test_serialize_bytes_passthrough(self):
        raw = b"\x00\x01\x02"
        assert _serialize_data(raw) == raw

    def test_serialize_bytearray(self):
        assert _serialize_data(bytearray(b"hello")) == b"hello"

    def test_serialize_dict(self):
        import json
        result = _serialize_data({"a": 1})
        assert isinstance(result, bytes)
        assert json.loads(result) == {"a": 1}

    def test_serialize_list(self):
        import json
        result = _serialize_data([1, 2, 3])
        assert isinstance(result, bytes)
        assert json.loads(result) == [1, 2, 3]

    def test_roundtrip_dict(self):
        original = {"username": "player1", "score": 42}
        assert _deserialize_data(_serialize_data(original)) == original

    def test_roundtrip_none(self):
        assert _deserialize_data(_serialize_data(None)) is None

    def test_roundtrip_raw_bytes(self):
        raw = b"\xff\xfe\xfd"
        assert _deserialize_data(_serialize_data(raw)) == raw

    def test_deserialize_str_fallback(self):
        import json
        # SQLite affinity edge case: BLOB returned as str
        assert _deserialize_data(json.dumps({"x": 1})) == {"x": 1}


# ---------------------------------------------------------------------------
# Unit tests — _BufferedMapping
# ---------------------------------------------------------------------------

class TestBufferedMapping:
    def test_setitem_marks_dirty(self):
        m = _BufferedMapping({})
        m["k"] = {"a": 1}
        assert "k" in m._dirty

    def test_delitem_marks_deleted(self):
        m = _BufferedMapping({"k": {"a": 1}})
        del m["k"]
        assert "k" in m._deleted
        assert "k" not in m._dirty

    def test_reinsert_clears_deleted(self):
        m = _BufferedMapping({"k": {"a": 1}})
        del m["k"]
        m["k"] = {"a": 2}
        assert "k" not in m._deleted
        assert "k" in m._dirty

    def test_pop_dirty_drains_both_sets(self):
        m = _BufferedMapping({"a": {"x": 1}})
        m["b"] = {"x": 2}
        del m["a"]
        upserts, deletes = m.pop_dirty()
        assert "b" in upserts
        assert "a" in deletes
        assert m.dirty_count == 0
        assert len(m._deleted) == 0

    def test_contains_is_ram_only(self):
        m = _BufferedMapping({"k": {}})
        assert "k" in m
        assert "missing" not in m

    def test_len(self):
        m = _BufferedMapping({"a": {}, "b": {}})
        assert len(m) == 2
        m["c"] = {}
        assert len(m) == 3
        del m["a"]
        assert len(m) == 2


# ---------------------------------------------------------------------------
# Correctness tests — SQLiteStorage
# ---------------------------------------------------------------------------

class TestSQLiteStorageCorrectness:

    def test_open_creates_db_file(self, db_path, store):
        assert db_path.exists()

    def test_store_and_retrieve_returns_cache_record(self, store):
        store.store_record("player:1", make_record(data={"username": "player1"}))
        result = store.get_record("player:1")
        assert isinstance(result, CacheRecord)
        assert result.data["username"] == "player1"

    def test_store_persists_after_flush(self, db_path, store):
        store.store_record("player:1", make_record(data={"score": 99}))
        store.flush()
        assert record_count_on_disk(db_path) == 1

    def test_stored_columns_match_schema(self, db_path, store):
        rec = make_record(data={"hello": "world"}, cast=dict)
        store.store_record("k", rec)
        store.flush()

        row = read_row_from_disk(db_path, "k")
        assert row["cast"] == "dict"
        assert row["data"] == {"hello": "world"}
        assert row["timestamp"] == pytest.approx(rec["timestamp"], abs=1.0)

    def test_cast_str_survives_flush_and_reload(self, db_path, store):
        store.store_record("k", make_record(cast=dict))
        store.flush()
        row = read_row_from_disk(db_path, "k")
        assert row["cast"] == "dict"

    def test_null_cast_stored_as_null(self, db_path, store):
        store.store_record("k", make_record(cast=None))
        store.flush()
        row = read_row_from_disk(db_path, "k")
        assert row["cast"] is None

    def test_update_record_refreshes_data(self, store):
        store.store_record("k", make_record(data={"a": 1}))
        store.update_record("k", {"data": {"a": 1, "b": 2}})
        result = store.get_record("k")
        assert result.data == {"a": 1, "b": 2}

    def test_upsert_overwrites_existing(self, db_path, store):
        store.store_record("k", make_record(data={"v": 1}))
        store.flush()
        store.store_record("k", make_record(data={"v": 2}))
        store.flush()
        row = read_row_from_disk(db_path, "k")
        assert row["data"]["v"] == 2
        assert record_count_on_disk(db_path) == 1   # no duplicate rows



    def test_erase_everything_clears_memory_and_disk(self, db_path, store):
        for i in range(5):
            store.store_record(f"k{i}", make_record())
        store.flush()
        store.erase_everything()
        assert len(store.records) == 0
        assert record_count_on_disk(db_path) == 0

    def test_infinite_expiry_roundtrip(self, store):
        """math.inf expiry must survive the 'math.inf' string encoding round-trip."""
        store.store_record("k", make_record(expiry=math.inf))
        result = store.get_record("k")
        # CacheRecord.__init__ decodes 'math.inf' back to math.inf
        assert result.expiry == math.inf
        assert not result.is_data_stale

    def test_finite_expiry_stale(self, store):
        """A record with a past expiry should be immediately stale."""
        store.store_record("k", make_record(expiry=-1))
        result = store.get_record("k")
        assert result.is_data_stale

    def test_get_record_raises_for_missing_key(self, store):
        with pytest.raises(KeyError):
            store.get_record("does-not-exist")

    def test_multiple_records_independent(self, store):
        store.store_record("p1", make_record(data={"username": "Alice"}))
        store.store_record("p2", make_record(data={"username": "Bob"}))
        assert store.get_record("p1").data["username"] == "Alice"
        assert store.get_record("p2").data["username"] == "Bob"

    def test_reload_from_disk(self, db_path, store):
        """Records flushed by one instance are visible to a freshly opened one."""
        store.store_record("player:1", make_record(data={"score": 55}))
        store.close()

        store2 = SQLiteStorage(str(db_path), flush_interval=60.0)
        result = store2.get_record("player:1")
        store2.close()

        assert isinstance(result, CacheRecord)
        assert result.data["score"] == 55

    def test_context_manager_flushes_on_exit(self, db_path):
        with SQLiteStorage(str(db_path), flush_interval=60.0) as s:
            s.store_record("k", make_record(data={"x": 42}))
        assert record_count_on_disk(db_path) == 1

    def test_dirty_threshold_triggers_flush(self, db_path):
        """Hitting dirty_threshold must flush without an explicit flush() call."""
        store = SQLiteStorage(str(db_path), flush_interval=60.0, dirty_threshold=10)
        for i in range(10):
            store.store_record(f"k{i}", make_record())
        time.sleep(0.1)
        count = record_count_on_disk(db_path)
        store.close()
        assert count == 10

    def test_write_then_delete_before_flush_leaves_nothing(self, db_path, store):
        store.store_record("k", make_record())
        del store.records["k"]
        store.flush()
        assert record_count_on_disk(db_path) == 0

    def test_concurrent_writes_are_safe(self, store):
        """Multiple threads writing distinct keys must not corrupt the mapping."""
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(50):
                    store.store_record(f"t{thread_id}:k{i}", make_record(data={"i": i}))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(store.records) == 4 * 50


# ---------------------------------------------------------------------------
# Performance benchmarks
# ---------------------------------------------------------------------------
#
# Thresholds are conservative — a modern laptop beats these by 10–50×.
# A failure here means something pathological happened: accidental per-write
# fsync, O(N²) loop, serialisation blowup, etc.

class TestSQLiteStoragePerformance:

    def test_bench_writes_are_sub_microsecond(self, store):
        """10 000 in-memory writes must complete in under 500 ms (50 µs/write).

        Pure RAM path: dict __setitem__ + set add + threshold check.
        50 µs/write is conservative enough to pass on Windows/CPython while
        still catching any regression that reintroduces per-write IO.
        """
        N = 10_000
        rec = make_record(data={"username": "player", "score": 100})

        start = time.perf_counter()
        for i in range(N):
            store.store_record(f"k{i}", rec)
        elapsed = time.perf_counter() - start

        per_write_us = (elapsed / N) * 1e6
        print(f"\n  {N} writes: {elapsed * 1000:.1f} ms total, {per_write_us:.2f} µs/write")
        assert elapsed < 0.5, (
            f"10 000 writes took {elapsed * 1000:.0f} ms — expected < 500 ms. "
            f"Writes should be pure RAM; check for accidental IO "
            f"(per-write IO would show ~1000+ ms here)."
        )

    def test_bench_reads_are_sub_microsecond(self, store):
        """10 000 in-memory reads must complete in under 50 ms (5 µs/read)."""
        N = 10_000
        rec = make_record(data={"username": "player", "score": 100})
        for i in range(N):
            store.store_record(f"k{i}", rec)

        start = time.perf_counter()
        for i in range(N):
            _ = store.get_record(f"k{i}")
        elapsed = time.perf_counter() - start

        per_read_us = (elapsed / N) * 1e6
        print(f"\n  {N} reads: {elapsed * 1000:.1f} ms total, {per_read_us:.2f} µs/read")
        assert elapsed < 0.05, (
            f"10 000 reads took {elapsed * 1000:.0f} ms — expected < 50 ms. "
            f"Reads should be O(1) dict lookups with zero IO."
        )

    def test_bench_flush_1000_records(self, store):
        """Flushing 1 000 dirty records must complete in under 500 ms."""
        N = 1_000
        for i in range(N):
            store.store_record(f"k{i}", make_record(data={"i": i}))

        start = time.perf_counter()
        store.flush()
        elapsed = time.perf_counter() - start

        print(f"\n  flush {N} records: {elapsed * 1000:.1f} ms")
        assert elapsed < 0.5, (
            f"Flushing {N} records took {elapsed * 1000:.0f} ms — expected < 500 ms."
        )

    def test_bench_flush_10000_records(self, store):
        """Flushing 10 000 dirty records must complete in under 2 s."""
        N = 10_000
        for i in range(N):
            store.store_record(f"k{i}", make_record(data={"i": i, "payload": "x" * 256}))

        start = time.perf_counter()
        store.flush()
        elapsed = time.perf_counter() - start

        print(f"\n  flush {N} records: {elapsed * 1000:.1f} ms")
        assert elapsed < 2.0, (
            f"Flushing {N} records took {elapsed * 1000:.0f} ms — expected < 2 000 ms."
        )

    def test_bench_batch_flush_faster_than_per_write_sqlite(self, db_path, store):
        """Batch flush must be at least 5× faster than naive per-write commits."""
        N = 500

        for i in range(N):
            store.store_record(f"k{i}", make_record(data={"score": i}))
        start = time.perf_counter()
        store.flush()
        batch_elapsed = time.perf_counter() - start

        naive_db = str(db_path.parent / "naive.db")
        conn = sqlite3.connect(naive_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_records (
                key TEXT PRIMARY KEY, "cast" TEXT,
                expiry REAL, timestamp REAL, data BLOB
            )
        """)
        start = time.perf_counter()
        for i in range(N):
            conn.execute(
                'INSERT OR REPLACE INTO cache_records '
                '(key, "cast", expiry, timestamp, data) VALUES (?, ?, ?, ?, ?)',
                (f"naive{i}", None, None, time.time(), b"{}"),
            )
            conn.commit()
        naive_elapsed = time.perf_counter() - start
        conn.close()

        ratio = naive_elapsed / batch_elapsed if batch_elapsed > 0 else float("inf")
        print(
            f"\n  batch flush {N}: {batch_elapsed * 1000:.1f} ms"
            f"\n  naive {N}×commit: {naive_elapsed * 1000:.1f} ms"
            f"\n  speedup: {ratio:.1f}×"
        )
        assert ratio >= 5, (
            f"Batch flush was only {ratio:.1f}× faster than per-write commits "
            f"(expected ≥ 5×). The write-behind buffer may not be working."
        )

    def test_bench_open_with_10000_existing_records(self, db_path, store):
        """Re-opening a 10 000-record DB must load in under 3 s."""
        N = 10_000
        for i in range(N):
            store.store_record(f"k{i}", make_record(data={"i": i}))
        store.close()

        start = time.perf_counter()
        s2 = SQLiteStorage(str(db_path), flush_interval=60.0)
        elapsed = time.perf_counter() - start
        s2.close()

        print(f"\n  open + load {N} records: {elapsed * 1000:.1f} ms")
        assert elapsed < 3.0, (
            f"Loading {N} records on open took {elapsed * 1000:.0f} ms — expected < 3 000 ms."
        )

    def test_bench_dirty_count_zero_after_flush(self, store):
        """Dirty set must be empty immediately after flush."""
        for i in range(200):
            store.store_record(f"k{i}", make_record())
        store.flush()
        assert store.records.dirty_count == 0, (
            "Dirty set non-empty after flush — pop_dirty() may not be clearing correctly."
        )
